import pytest
from langchain_core.documents import Document

from rag_pipeline.chunking import split_documents
from rag_pipeline.config import ConfigError
from rag_pipeline.ingestion import IngestionError, load_pdf, load_pdfs

TEXT = " ".join(f"Sentence number {i} about the refund policy." for i in range(200))


def doc(text=TEXT, source="a.pdf", page=1):
    return Document(page_content=text, metadata={"source": source, "page": page})


@pytest.mark.parametrize("size,overlap", [(200, 0), (300, 50), (500, 100)])
def test_chunks_respect_chunk_size(size, overlap):
    chunks = split_documents([doc()], size, overlap)
    assert len(chunks) > 1
    assert all(len(c.page_content) <= size for c in chunks)


def test_smaller_chunk_size_gives_more_chunks():
    assert len(split_documents([doc()], 200, 20)) > len(split_documents([doc()], 800, 20))


def test_overlap_repeats_text_between_neighbouring_chunks():
    no_overlap = split_documents([doc()], 300, 0)
    with_overlap = split_documents([doc()], 300, 100)
    assert len(with_overlap) > len(no_overlap)
    # With overlap, each chunk starts before the previous one ends.
    for prev, nxt in zip(with_overlap, with_overlap[1:]):
        prev_end = prev.metadata["start_index"] + len(prev.page_content)
        assert nxt.metadata["start_index"] < prev_end


@pytest.mark.parametrize("size,overlap", [(0, 0), (100, 100), (100, -1)])
def test_invalid_params_rejected(size, overlap):
    with pytest.raises(ConfigError):
        split_documents([doc()], size, overlap)


def test_metadata_preserved_and_chunk_index_per_source():
    chunks = split_documents([doc(source="a.pdf", page=1), doc(source="a.pdf", page=2),
                              doc(source="b.pdf", page=3)], 300, 30)
    for c in chunks:
        assert c.metadata["source"] in {"a.pdf", "b.pdf"}
        assert c.metadata["page"] in {1, 2, 3}
    a_idx = [c.metadata["chunk_index"] for c in chunks if c.metadata["source"] == "a.pdf"]
    b_idx = [c.metadata["chunk_index"] for c in chunks if c.metadata["source"] == "b.pdf"]
    assert a_idx == list(range(len(a_idx)))
    assert b_idx == list(range(len(b_idx)))


# --- PDF ingestion (uses the real sample PDFs, no network) -----------------------

def test_three_sample_pdfs_load_with_metadata(sample_pdf_dir):
    pages = load_pdfs(sample_pdf_dir, min_documents=3)
    sources = {p.metadata["source"] for p in pages}
    assert len(sources) == 3
    for p in pages:
        assert p.metadata["page"] >= 1  # human (1-based) page numbers
        assert p.page_content.strip()


def test_sample_pdf_text_contains_known_fact(sample_pdf_dir):
    pages = load_pdf(sample_pdf_dir / "brightleaf_employee_handbook.pdf")
    assert any("24 days of paid annual leave" in " ".join(p.page_content.split()) for p in pages)


def test_too_few_pdfs_is_an_error(tmp_path):
    with pytest.raises(IngestionError, match="at least 3"):
        load_pdfs(tmp_path, min_documents=3)


def test_corrupt_pdf_is_reported_not_skipped(tmp_path):
    (tmp_path / "broken.pdf").write_bytes(b"this is not a pdf")
    with pytest.raises(IngestionError, match="broken.pdf"):
        load_pdfs(tmp_path, min_documents=1)


def test_pdf_without_text_is_rejected(tmp_path):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)  # like a scanned page: no text layer
    with open(tmp_path / "blank.pdf", "wb") as f:
        writer.write(f)
    with pytest.raises(IngestionError, match="no extractable text"):
        load_pdf(tmp_path / "blank.pdf")
