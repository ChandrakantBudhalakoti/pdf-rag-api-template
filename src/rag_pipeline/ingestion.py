"""PDF loading: read every PDF in a folder into LangChain `Document`s (one per page)."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# A page with fewer non-whitespace characters than this is treated as "no text"
# (typically a scanned image page, which would need OCR).
MIN_PAGE_CHARS = 20


class IngestionError(RuntimeError):
    """Raised when PDFs are missing, unreadable, or contain no extractable text."""


def find_pdfs(pdf_dir: Path) -> list[Path]:
    if not pdf_dir.is_dir():
        raise IngestionError(f"PDF folder not found: {pdf_dir}")
    return sorted(p for p in pdf_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def load_pdf(path: Path) -> list[Document]:
    """Load one PDF. Returns only pages with real text; raises if none have any.

    Metadata on every page: `source` (file name), `page` (1-based page number),
    `total_pages`.
    """
    try:
        raw_pages = PyPDFLoader(str(path)).load()
    except Exception as exc:  # pypdf raises many different error types
        raise IngestionError(f"Could not read PDF '{path.name}': {exc}") from exc

    pages: list[Document] = []
    for raw in raw_pages:
        text = raw.page_content.strip()
        page_number = int(raw.metadata.get("page", 0)) + 1  # PyPDFLoader is 0-based
        if len("".join(text.split())) < MIN_PAGE_CHARS:
            logger.warning("%s page %d has no extractable text (scanned image?) - skipped",
                           path.name, page_number)
            continue
        pages.append(
            Document(
                page_content=text,
                metadata={
                    "source": path.name,
                    "page": page_number,
                    "total_pages": len(raw_pages),
                },
            )
        )

    if not pages:
        raise IngestionError(
            f"'{path.name}' contains no extractable text. It may be a scanned PDF, "
            "which needs OCR before it can be ingested."
        )
    return pages


def load_pdfs(pdf_dir: Path, min_documents: int = 1) -> list[Document]:
    """Load all PDFs in `pdf_dir`. Fails loudly if any PDF is unusable."""
    paths = find_pdfs(pdf_dir)
    if len(paths) < min_documents:
        raise IngestionError(
            f"Expected at least {min_documents} PDF(s) in {pdf_dir}, found {len(paths)}."
        )

    documents: list[Document] = []
    errors: list[str] = []
    for path in paths:
        try:
            documents.extend(load_pdf(path))
        except IngestionError as exc:
            errors.append(str(exc))

    if errors:
        # Never silently skip a broken file: the index would be incomplete.
        raise IngestionError("Some PDFs could not be ingested:\n  - " + "\n  - ".join(errors))
    return documents
