"""Split page documents into overlapping chunks suitable for embedding."""

from __future__ import annotations

from collections import defaultdict

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_pipeline.config import validate_chunk_params


def split_documents(
    documents: list[Document], chunk_size: int, chunk_overlap: int
) -> list[Document]:
    """Split documents into chunks of at most `chunk_size` characters.

    Consecutive chunks share up to `chunk_overlap` characters so that a sentence
    cut at a boundary still appears whole in one of the chunks.

    Every chunk keeps its page's metadata (source, page, ...) and gets:
      - `chunk_index`: position of the chunk within its source file (0-based)
      - `start_index`: character offset of the chunk within its page
    """
    validate_chunk_params(chunk_size, chunk_overlap)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
        # Try paragraph breaks first, then lines, sentences, words, characters.
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    counters: dict[str, int] = defaultdict(int)
    for chunk in chunks:
        source = chunk.metadata.get("source", "unknown")
        chunk.metadata["chunk_index"] = counters[source]
        counters[source] += 1
    return chunks
