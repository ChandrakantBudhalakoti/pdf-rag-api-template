"""HTTP API (FastAPI) over the same pipeline the CLI uses.

    uvicorn rag_pipeline.api:app --reload          # local development
    open http://localhost:8000/docs                # interactive API docs (Swagger UI)

Endpoints:
    GET  /health      liveness check (no database or AI provider calls)
    GET  /status      provider, models, database and index status
    GET  /documents   PDFs currently in PDF_DIR
    POST /documents   upload a PDF into PDF_DIR (run POST /ingest afterwards)
    POST /ingest      rebuild the index from every PDF in PDF_DIR
    POST /search      similarity search only (no LLM)
    POST /ask         full RAG answer with sources

If SERVICE_API_KEY is set, every endpoint except /health requires the header
`X-API-Key: <SERVICE_API_KEY>`.
"""

from __future__ import annotations

import re
import secrets
import threading
import warnings
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Security, UploadFile
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from rag_pipeline import __version__
from rag_pipeline.config import ConfigError, Settings
from rag_pipeline.ingestion import IngestionError, find_pdfs
from rag_pipeline.pipeline import LLMError, RagPipeline, ingest
from rag_pipeline.retrieval import RetrievedChunk
from rag_pipeline.vectorstore import DatabaseError, get_status

warnings.filterwarnings("ignore", category=DeprecationWarning)

# --------------------------------------------------------------------------- schemas


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000, examples=["What is the notice period after probation?"])
    k: int | None = Field(default=None, ge=1, le=20, description="chunks to retrieve (default TOP_K)")
    include_chunks: bool = Field(default=False, description="also return the retrieved chunks")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, examples=["sick leave"])
    k: int | None = Field(default=None, ge=1, le=20)


class Chunk(BaseModel):
    reference: str
    source: str
    page: int | None
    distance: float = Field(description="cosine distance: 0 = identical meaning, larger = less similar")
    text: str


class AskResponse(BaseModel):
    question: str
    answer: str
    found: bool
    sources: list[str]
    chunks: list[Chunk] | None = None


class SearchResponse(BaseModel):
    query: str
    chunks: list[Chunk]


class IngestResponse(BaseModel):
    files: list[str]
    pages: int
    chunks: int
    collection: str


class UploadResponse(BaseModel):
    filename: str
    bytes: int
    message: str


def _chunk(c: RetrievedChunk) -> Chunk:
    return Chunk(reference=c.reference, source=c.source, page=c.page, distance=round(c.distance, 4),
                 text=c.document.page_content)


# --------------------------------------------------------------------------- app state


class ServiceState:
    """Settings plus one shared RagPipeline, created on first use and rebuilt after ingestion."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._pipeline: RagPipeline | None = None
        self._lock = threading.Lock()

    def pipeline(self) -> RagPipeline:
        with self._lock:
            if self._pipeline is None:
                self._pipeline = RagPipeline(self.settings)
            return self._pipeline

    def reingest(self):
        # The lock prevents two rebuilds at once. Questions already in flight may briefly see an
        # empty collection while it is replaced (acceptable for a small, single-tenant index).
        with self._lock:
            result = ingest(self.settings)
            self._pipeline = None  # reopen the store (embedding model / collection may have changed)
            return result


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_pdf_name(filename: str | None) -> str:
    name = _SAFE_NAME.sub("_", Path(filename or "").name).strip("._")
    if not name.lower().endswith(".pdf") or len(name) <= 4:
        raise HTTPException(400, "Only .pdf files can be uploaded")
    return name


# --------------------------------------------------------------------------- app factory


def create_app(settings_factory: Callable[[], Settings] = Settings.from_env) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = ServiceState(settings_factory())  # fails fast on invalid configuration
        yield

    app = FastAPI(
        title="RAG Pipeline as a Service",
        version=__version__,
        description="Ask questions about your PDFs. Answers are grounded in the documents and cite file + page.",
        lifespan=lifespan,
    )

    def service(request: Request) -> ServiceState:
        return request.app.state.service

    # Declared as a security scheme so /docs shows an "Authorize" button for entering the key.
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False,
                                  description="Only needed when SERVICE_API_KEY is set on the server")

    def require_api_key(key: str | None = Security(api_key_header), svc: ServiceState = Depends(service)) -> None:
        expected = svc.settings.service_api_key
        if expected and not secrets.compare_digest(key or "", expected):
            raise HTTPException(401, "Missing or invalid X-API-Key header")

    # Map pipeline errors to HTTP status codes with the same clear messages the CLI prints.
    for exc_type, code in ((ConfigError, 500), (DatabaseError, 503), (LLMError, 502), (IngestionError, 400)):
        app.add_exception_handler(
            exc_type, lambda _req, exc, code=code: JSONResponse(status_code=code, content={"detail": str(exc)})
        )

    protected = [Depends(require_api_key)]

    @app.get("/health", tags=["service"])
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/status", tags=["service"], dependencies=protected)
    def status(svc: ServiceState = Depends(service)) -> dict:
        s = svc.settings
        db = get_status(s)
        return {
            "provider": s.provider,
            "embedding_model": s.embedding_model,
            "llm_model": s.llm_model,
            "chunk_size": s.chunk_size,
            "chunk_overlap": s.chunk_overlap,
            "top_k": s.top_k,
            "collection": s.collection_name,
            "database": {"server_version": db.server_version, "pgvector_version": db.pgvector_version},
            "index": {
                "exists": db.collection_exists,
                "indexed_with": (db.collection_metadata or {}).get("embedding_model"),
                "chunks": sum(db.chunk_counts.values()),
                "chunks_per_source": db.chunk_counts,
            },
        }

    @app.get("/documents", tags=["documents"], dependencies=protected)
    def list_documents(svc: ServiceState = Depends(service)) -> dict:
        return {"pdf_dir": svc.settings.pdf_dir.name, "files": [p.name for p in find_pdfs(svc.settings.pdf_dir)]}

    @app.post("/documents", tags=["documents"], dependencies=protected, status_code=201)
    def upload_document(file: UploadFile = File(...), svc: ServiceState = Depends(service)) -> UploadResponse:
        name = _safe_pdf_name(file.filename)
        limit = svc.settings.max_upload_mb * 1024 * 1024
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"File is larger than MAX_UPLOAD_MB ({svc.settings.max_upload_mb} MB)")
        if not data.startswith(b"%PDF"):
            raise HTTPException(400, "The file is not a valid PDF")
        svc.settings.pdf_dir.mkdir(parents=True, exist_ok=True)
        (svc.settings.pdf_dir / name).write_bytes(data)
        return UploadResponse(filename=name, bytes=len(data),
                              message="Saved. Call POST /ingest to add it to the index.")

    @app.post("/ingest", tags=["documents"], dependencies=protected)
    def run_ingest(svc: ServiceState = Depends(service)) -> IngestResponse:
        result = svc.reingest()
        return IngestResponse(files=result.files, pages=result.pages, chunks=result.chunks,
                              collection=svc.settings.collection_name)

    @app.post("/search", tags=["query"], dependencies=protected)
    def search(req: SearchRequest, svc: ServiceState = Depends(service)) -> SearchResponse:
        chunks = svc.pipeline().search(req.query, req.k)
        return SearchResponse(query=req.query, chunks=[_chunk(c) for c in chunks])

    @app.post("/ask", tags=["query"], dependencies=protected)
    def ask(req: AskRequest, svc: ServiceState = Depends(service)) -> AskResponse:
        try:
            result = svc.pipeline().ask(req.question, req.k)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return AskResponse(
            question=result.question,
            answer=result.answer,
            found=result.found,
            sources=result.references,
            chunks=[_chunk(c) for c in result.retrieved] if req.include_chunks else None,
        )

    return app


app = create_app()
