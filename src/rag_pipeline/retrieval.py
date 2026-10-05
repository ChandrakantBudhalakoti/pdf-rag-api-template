"""Similarity search over pgvector and formatting of retrieved chunks."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_postgres import PGVector


@dataclass
class RetrievedChunk:
    document: Document
    distance: float  # cosine distance: 0 = identical meaning, larger = less similar

    @property
    def source(self) -> str:
        return self.document.metadata.get("source", "unknown")

    @property
    def page(self) -> int | None:
        return self.document.metadata.get("page")

    @property
    def reference(self) -> str:
        return f"{self.source}, page {self.page}" if self.page else self.source


def retrieve(store: PGVector, question: str, k: int) -> list[RetrievedChunk]:
    """Embed the question and return the k nearest chunks (closest first)."""
    results = store.similarity_search_with_score(question, k=k)
    return [RetrievedChunk(document=doc, distance=float(score)) for doc, score in results]


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Render chunks as numbered, source-labelled blocks for the LLM prompt."""
    blocks = [
        f"[{i}] Source: {c.reference}\n{c.document.page_content}"
        for i, c in enumerate(chunks, start=1)
    ]
    return "\n\n---\n\n".join(blocks)
