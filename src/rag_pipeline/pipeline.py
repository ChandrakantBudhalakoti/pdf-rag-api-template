"""The RAG pipeline: ingest PDFs, and answer questions grounded in them."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import openai
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.rate_limiters import InMemoryRateLimiter

from rag_pipeline.chunking import split_documents
from rag_pipeline.config import Settings
from rag_pipeline.embeddings import get_embeddings
from rag_pipeline.ingestion import load_pdfs
from rag_pipeline.retrieval import RetrievedChunk, format_context, retrieve
from rag_pipeline.vectorstore import get_vector_store, rebuild_collection

logger = logging.getLogger(__name__)

NOT_FOUND_MESSAGE = "I could not find the answer in the provided documents."

SYSTEM_PROMPT = f"""You are a precise assistant that answers questions using ONLY the \
document excerpts provided in the context.

Rules:
1. Use only facts stated in the context. Never use outside or general knowledge.
2. If the context does not contain the information needed to answer, reply with exactly:
   "{NOT_FOUND_MESSAGE}"
   Do not guess, estimate, or answer a related-but-different question.
3. If the question has several parts, answer every part that the context supports, and \
say which part is not covered.
4. Quote numbers, dates, prices and names exactly as they appear in the context.
5. Be concise: one to three sentences.
6. After the answer, add a line "Sources: [n], [m]" listing the numbers of the context \
excerpts you actually used. Omit this line if you replied with the not-found message."""

HUMAN_PROMPT = """Context:
{context}

Question: {question}"""

# The trailing "Sources: [1], [3]" marker, on its own line or at the end of the last sentence.
_SOURCES_MARKER = re.compile(
    r"\s*\bSources?:\s*((?:\[?\d+\]?(?:\s*(?:,|;|and)\s*)?)+)\.?\s*$", re.IGNORECASE
)


class LLMError(RuntimeError):
    """Raised when the AI provider call fails (auth, quota, network, model name)."""


def _provider_errors() -> tuple[type[BaseException], ...]:
    """Exception types raised by the OpenAI and Gemini client libraries."""
    errors: list[type[BaseException]] = [openai.OpenAIError]
    try:
        from google.genai.errors import APIError
        from langchain_google_genai._common import GoogleGenerativeAIError

        errors += [APIError, GoogleGenerativeAIError]
    except ImportError:
        pass
    from langchain_core.exceptions import ModelError  # common base used by langchain-google-genai

    errors.append(ModelError)
    return tuple(errors)


PROVIDER_ERRORS = _provider_errors()


def _wrap_provider_error(exc: Exception, settings: Settings) -> LLMError:
    """Turn OpenAI / Gemini exceptions into one clear, actionable message."""
    name = settings.provider
    text = f"{type(exc).__name__}: {exc}"
    lowered = text.lower()
    if isinstance(exc, openai.AuthenticationError) or any(
        s in lowered for s in ("401", "api key not valid", "api_key_invalid", "permission_denied", "403")
    ):
        return LLMError(f"{name} rejected the API key. Check the key in .env. ({text[:300]})")
    if isinstance(exc, openai.RateLimitError) or any(
        s in lowered for s in ("429", "rate limit", "resource_exhausted", "quota")
    ):
        return LLMError(f"{name} rate limit or quota exceeded. Wait a minute or check billing/credits. "
                        f"({text[:300]})")
    if isinstance(exc, openai.NotFoundError) or any(s in lowered for s in ("404", "not_found", "not found")):
        return LLMError(f"{name} model not found. Check EMBEDDING_MODEL / LLM_MODEL. ({text[:300]})")
    if isinstance(exc, openai.APIConnectionError) or "connect" in lowered:
        return LLMError(f"Could not reach the {name} API. Check your internet connection/proxy.")
    return LLMError(f"{name} API error: {text[:500]}")


def get_chat_model(settings: Settings) -> BaseChatModel:
    """Chat model for the active provider. temperature=0 for deterministic, factual answers."""
    settings.require_api_key()
    # Optional client-side pacing, e.g. for the Gemini free tier's requests-per-minute limit.
    rate_limiter = None
    if settings.llm_requests_per_minute:
        rate_limiter = InMemoryRateLimiter(requests_per_second=settings.llm_requests_per_minute / 60)

    if settings.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        # The Google SDK logs an "automatic function calling" advisory on every call;
        # this pipeline uses no function calling, so it is noise.
        logging.getLogger("google_genai.models").setLevel(logging.ERROR)
        return ChatGoogleGenerativeAI(model=settings.llm_model, google_api_key=settings.api_key,
                                      temperature=0, max_retries=3, rate_limiter=rate_limiter)

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=settings.llm_model, api_key=settings.api_key, temperature=0, max_retries=3,
                      rate_limiter=rate_limiter)


@dataclass
class IngestResult:
    files: list[str]
    pages: int
    chunks: int


@dataclass
class RagAnswer:
    question: str
    answer: str
    cited: list[RetrievedChunk] = field(default_factory=list)  # chunks the LLM said it used
    retrieved: list[RetrievedChunk] = field(default_factory=list)  # everything retrieved

    @property
    def found(self) -> bool:
        return NOT_FOUND_MESSAGE.lower().rstrip(".") not in self.answer.lower()

    @property
    def references(self) -> list[str]:
        refs: dict[str, None] = {}
        for c in self.cited:
            refs.setdefault(c.reference, None)
        return list(refs)


def split_answer_and_citations(raw: str, retrieved: list[RetrievedChunk]) -> tuple[str, list[RetrievedChunk]]:
    """Separate the trailing "Sources: [1], [3]" marker from the answer text.

    Returns the clean answer and the retrieved chunks the model cited. Only numbers
    that refer to actually retrieved chunks are kept.
    """
    match = _SOURCES_MARKER.search(raw)
    if not match:
        return raw.strip(), []
    answer = (raw[: match.start()] + raw[match.end():]).strip()
    numbers = [int(n) for n in re.findall(r"\d+", match.group(1))]
    cited = [retrieved[n - 1] for n in dict.fromkeys(numbers) if 1 <= n <= len(retrieved)]
    return answer, cited


def ingest(settings: Settings, min_documents: int = 3) -> IngestResult:
    """PDFs -> pages -> chunks -> embeddings -> pgvector (collection rebuilt)."""
    pages = load_pdfs(settings.pdf_dir, min_documents=min_documents)
    chunks = split_documents(pages, settings.chunk_size, settings.chunk_overlap)
    try:
        stored = rebuild_collection(settings, get_embeddings(settings), chunks)
    except PROVIDER_ERRORS as exc:
        raise _wrap_provider_error(exc, settings) from exc
    return IngestResult(
        files=sorted({p.metadata["source"] for p in pages}),
        pages=len(pages),
        chunks=stored,
    )


class RagPipeline:
    """Question answering over the ingested collection. Reuse one instance for many questions."""

    def __init__(self, settings: Settings):
        self.settings = settings
        settings.require_api_key()
        self.store = get_vector_store(settings, get_embeddings(settings))
        llm = get_chat_model(settings)
        prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)])
        self.chain = prompt | llm | StrOutputParser()

    def search(self, question: str, k: int | None = None) -> list[RetrievedChunk]:
        try:
            return retrieve(self.store, question, k or self.settings.top_k)
        except PROVIDER_ERRORS as exc:
            raise _wrap_provider_error(exc, self.settings) from exc

    def ask(self, question: str, k: int | None = None) -> RagAnswer:
        question = question.strip()
        if not question:
            raise ValueError("Question must not be empty")

        retrieved = self.search(question, k)
        if not retrieved:
            return RagAnswer(question, NOT_FOUND_MESSAGE)

        try:
            raw = self.chain.invoke({"context": format_context(retrieved), "question": question})
        except PROVIDER_ERRORS as exc:
            raise _wrap_provider_error(exc, self.settings) from exc

        answer, cited = split_answer_and_citations(raw, retrieved)
        result = RagAnswer(question, answer, cited, retrieved)
        if not result.found:
            result.cited = []  # nothing was used, so nothing to cite
        return result
