"""Embedding model factory. Provider comes from AI_PROVIDER, model from EMBEDDING_MODEL."""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from rag_pipeline.config import Settings

# Known embedding models and their vector sizes (for information).
# Any other model name is passed through to the provider unchanged.
KNOWN_EMBEDDING_MODELS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "gemini-embedding-001": 3072,
}


def get_embeddings(settings: Settings) -> Embeddings:
    settings.require_api_key()
    if settings.provider == "gemini":
        # Imported lazily so the OpenAI path does not need the Google SDK loaded.
        # The class embeds documents with task type RETRIEVAL_DOCUMENT and queries
        # with RETRIEVAL_QUERY automatically, which is what retrieval needs.
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(model=settings.embedding_model, google_api_key=settings.api_key)

    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.api_key, max_retries=3)
