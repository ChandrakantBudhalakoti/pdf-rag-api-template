from langchain_core.documents import Document

from rag_pipeline.pipeline import SYSTEM_PROMPT, NOT_FOUND_MESSAGE, split_answer_and_citations
from rag_pipeline.retrieval import RetrievedChunk, format_context
from rag_pipeline.vectorstore import chunk_id


def chunk(source, page, text="some text"):
    return RetrievedChunk(Document(page_content=text, metadata={"source": source, "page": page}), 0.1)


RETRIEVED = [chunk("a.pdf", 1), chunk("b.pdf", 2), chunk("c.pdf", 3)]


def test_citations_are_parsed_and_removed_from_answer():
    answer, cited = split_answer_and_citations("The CEO is Asha Menon.\nSources: [1], [3]", RETRIEVED)
    assert answer == "The CEO is Asha Menon."
    assert [c.reference for c in cited] == ["a.pdf, page 1", "c.pdf, page 3"]


def test_out_of_range_and_duplicate_citations_are_ignored():
    _, cited = split_answer_and_citations("x\nSources: [2], [2], [9]", RETRIEVED)
    assert [c.reference for c in cited] == ["b.pdf, page 2"]


def test_answer_without_sources_line():
    answer, cited = split_answer_and_citations(NOT_FOUND_MESSAGE, RETRIEVED)
    assert answer == NOT_FOUND_MESSAGE and cited == []


def test_context_is_numbered_and_labelled_with_sources():
    ctx = format_context(RETRIEVED)
    assert "[1] Source: a.pdf, page 1" in ctx
    assert "[3] Source: c.pdf, page 3" in ctx


def test_prompt_enforces_grounding_and_not_found_message():
    assert NOT_FOUND_MESSAGE in SYSTEM_PROMPT
    assert "ONLY" in SYSTEM_PROMPT


def test_chunk_ids_are_deterministic_and_distinct():
    a = Document(page_content="hello", metadata={"source": "a.pdf", "page": 1, "chunk_index": 0, "start_index": 0})
    a2 = Document(page_content="hello", metadata=dict(a.metadata))
    b = Document(page_content="hello", metadata={**a.metadata, "chunk_index": 1})
    assert chunk_id(a) == chunk_id(a2)
    assert chunk_id(a) != chunk_id(b)


def test_inline_sources_marker_is_parsed():
    answer, cited = split_answer_and_citations("Founded in 2016 in Pune. Sources: [1]", RETRIEVED)
    assert answer == "Founded in 2016 in Pune."
    assert [c.reference for c in cited] == ["a.pdf, page 1"]


def test_sources_marker_variants():
    variants = ("x\nSources: [1] and [2].", "x Source: 1, 2", "x\n\nSOURCES: [1]; [2]\n")
    for raw in variants:
        answer, cited = split_answer_and_citations(raw, RETRIEVED)
        assert answer == "x", raw
        assert [c.reference for c in cited] == ["a.pdf, page 1", "b.pdf, page 2"], raw


def test_word_sources_inside_answer_is_not_treated_as_marker():
    raw = "Sources: of revenue are not listed, but 12 days of sick leave apply."
    answer, cited = split_answer_and_citations(raw, RETRIEVED)
    assert answer == raw and cited == []
