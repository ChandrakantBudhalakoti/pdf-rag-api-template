"""PostgreSQL + pgvector storage via `langchain_postgres.PGVector`.

Tables (created automatically by langchain-postgres):
  - langchain_pg_collection: one row per collection (name + metadata)
  - langchain_pg_embedding:  one row per chunk (text, vector, metadata, id)

Re-ingestion strategy: all chunks are embedded FIRST; only if that succeeds is
this project's collection (and only this collection) deleted and rebuilt. Chunk
ids are deterministic, so re-running ingestion never produces duplicates and an
OpenAI failure never leaves you with an empty index.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

import psycopg
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector

from rag_pipeline.config import Settings


class DatabaseError(RuntimeError):
    """Raised for connection problems, missing pgvector, or a missing/stale index."""


@dataclass
class DatabaseStatus:
    server_version: str
    pgvector_version: str | None
    collection_exists: bool
    collection_metadata: dict | None
    chunk_counts: dict[str, int]


def _connect(settings: Settings) -> psycopg.Connection:
    try:
        return psycopg.connect(settings.psycopg_url, connect_timeout=5)
    except psycopg.OperationalError as exc:
        raise DatabaseError(
            "Cannot connect to PostgreSQL at DATABASE_URL. Is the database running?\n"
            "  Docker:       docker compose up -d\n"
            "  No Docker:    python scripts/local_postgres.py start\n"
            f"  Driver error: {exc}"
        ) from exc


def ensure_pgvector(settings: Settings) -> str:
    """Enable the pgvector extension if needed and return its version."""
    with _connect(settings) as conn:
        try:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except psycopg.Error as exc:
            raise DatabaseError(
                "The pgvector extension is not available on this PostgreSQL server. "
                "Use the pgvector/pgvector Docker image or install pgvector."
            ) from exc
        row = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
        return row[0]


def get_status(settings: Settings) -> DatabaseStatus:
    """Read-only view of the database and this project's collection."""
    with _connect(settings) as conn:
        server_version = conn.execute("SHOW server_version").fetchone()[0]
        row = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
        pgvector_version = row[0] if row else None

        tables = conn.execute("SELECT to_regclass('langchain_pg_collection')").fetchone()[0]
        if tables is None:
            return DatabaseStatus(server_version, pgvector_version, False, None, {})

        row = conn.execute(
            "SELECT uuid, cmetadata FROM langchain_pg_collection WHERE name = %s",
            (settings.collection_name,),
        ).fetchone()
        if row is None:
            return DatabaseStatus(server_version, pgvector_version, False, None, {})

        counts = conn.execute(
            "SELECT cmetadata->>'source', count(*) FROM langchain_pg_embedding "
            "WHERE collection_id = %s GROUP BY 1 ORDER BY 1",
            (row[0],),
        ).fetchall()
        return DatabaseStatus(server_version, pgvector_version, True, row[1] or {}, dict(counts))


def chunk_id(chunk: Document) -> str:
    """Deterministic id: same source + page + position + text => same id."""
    key = "|".join(
        str(chunk.metadata.get(k, "")) for k in ("source", "page", "chunk_index", "start_index")
    )
    digest = hashlib.sha256((key + "|" + chunk.page_content).encode("utf-8")).hexdigest()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, digest))


def _open_store(settings: Settings, embeddings: Embeddings, collection_metadata: dict | None = None) -> PGVector:
    return PGVector(
        embeddings=embeddings,
        connection=settings.database_url,
        collection_name=settings.collection_name,
        collection_metadata=collection_metadata,
        use_jsonb=True,
        create_extension=False,  # done explicitly in ensure_pgvector()
    )


def rebuild_collection(settings: Settings, embeddings: Embeddings, chunks: list[Document]) -> int:
    """Embed `chunks` and replace the contents of this project's collection."""
    if not chunks:
        raise ValueError("No chunks to store")
    ensure_pgvector(settings)

    texts = [c.page_content for c in chunks]
    vectors = embeddings.embed_documents(texts)  # may raise OpenAI errors -> DB untouched
    ids = [chunk_id(c) for c in chunks]

    metadata = {
        "provider": settings.provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": len(vectors[0]),
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "sources": sorted({c.metadata["source"] for c in chunks}),
    }
    store = _open_store(settings, embeddings, metadata)
    store.delete_collection()  # removes only rows of THIS collection
    store.create_collection()
    store.add_embeddings(texts=texts, embeddings=vectors, metadatas=[c.metadata for c in chunks], ids=ids)
    return len(ids)


def get_vector_store(settings: Settings, embeddings: Embeddings) -> PGVector:
    """Open the existing collection for querying, after checking it is usable."""
    status = get_status(settings)
    if not status.collection_exists or not status.chunk_counts:
        raise DatabaseError(
            f"Collection '{settings.collection_name}' is empty or missing. "
            "Run ingestion first:  python -m rag_pipeline.cli ingest"
        )
    indexed_model = (status.collection_metadata or {}).get("embedding_model")
    if indexed_model and indexed_model != settings.embedding_model:
        raise DatabaseError(
            f"The collection was indexed with '{indexed_model}' but EMBEDDING_MODEL is "
            f"'{settings.embedding_model}'. Query and document vectors must come from the "
            "same model: re-run  python -m rag_pipeline.cli ingest"
        )
    return _open_store(settings, embeddings)
