"""Integration test against the REAL PostgreSQL/pgvector database (no OpenAI).

A tiny deterministic bag-of-words embedding is used ONLY here, in a separate
throwaway collection, so storage/search/de-duplication can be verified without
API credits. The real pipeline always uses real OpenAI or Gemini embeddings.
Skipped automatically when PostgreSQL is not reachable.
"""

import hashlib
import math
import re

import pytest
from langchain_core.embeddings import Embeddings

from rag_pipeline.chunking import split_documents
from rag_pipeline.config import Settings
from rag_pipeline.ingestion import load_pdfs
from rag_pipeline.retrieval import retrieve
from rag_pipeline.vectorstore import DatabaseError, ensure_pgvector, get_status, get_vector_store, rebuild_collection

DIM = 256


class HashingTestEmbeddings(Embeddings):
    """Test-only: hashes words into a fixed-size normalized vector."""

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts):
        return [self._embed(t) for t in texts]

    def embed_query(self, text):
        return self._embed(text)


@pytest.fixture
def settings():
    s = Settings.from_env(env={"COLLECTION_NAME": "pytest_integration", "EMBEDDING_MODEL": "test-hashing",
                               "CHUNK_SIZE": "400", "CHUNK_OVERLAP": "50"})
    try:
        ensure_pgvector(s)
    except DatabaseError:
        pytest.skip("PostgreSQL is not running")
    yield s
    try:  # remove only the throwaway test collection
        get_vector_store(s, HashingTestEmbeddings()).delete_collection()
    except DatabaseError:
        pass


def test_store_search_and_reingest_without_duplicates(settings, sample_pdf_dir):
    emb = HashingTestEmbeddings()
    chunks = split_documents(load_pdfs(sample_pdf_dir, 3), settings.chunk_size, settings.chunk_overlap)

    rebuild_collection(settings, emb, chunks)
    first = get_status(settings)
    assert first.pgvector_version
    assert len(first.chunk_counts) == 3
    assert sum(first.chunk_counts.values()) == len(chunks)
    assert first.collection_metadata["embedding_model"] == "test-hashing"

    rebuild_collection(settings, emb, chunks)  # re-ingest
    assert get_status(settings).chunk_counts == first.chunk_counts  # no duplicates

    hits = retrieve(get_vector_store(settings, emb), "paid sick leave days per calendar year", k=2)
    assert hits[0].source == "brightleaf_employee_handbook.pdf"
    assert hits[0].page == 1


def test_query_with_different_embedding_model_is_refused(settings, sample_pdf_dir):
    emb = HashingTestEmbeddings()
    chunks = split_documents(load_pdfs(sample_pdf_dir, 3), settings.chunk_size, settings.chunk_overlap)
    rebuild_collection(settings, emb, chunks)
    other = Settings.from_env(env={"COLLECTION_NAME": settings.collection_name,
                                   "EMBEDDING_MODEL": "text-embedding-3-large"})
    with pytest.raises(DatabaseError, match="re-run"):
        get_vector_store(other, emb)
