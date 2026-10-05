"""HTTP API tests. The pipeline is replaced by a fake, so no API key or database is needed."""

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from rag_pipeline import api
from rag_pipeline.config import Settings
from rag_pipeline.pipeline import NOT_FOUND_MESSAGE, IngestResult, LLMError, RagAnswer
from rag_pipeline.retrieval import RetrievedChunk
from rag_pipeline.vectorstore import DatabaseError

CHUNKS = [
    RetrievedChunk(Document(page_content="Notice period is 60 days.", metadata={"source": "h.pdf", "page": 2}), 0.12),
    RetrievedChunk(Document(page_content="Other text.", metadata={"source": "p.pdf", "page": 1}), 0.4),
]


class FakePipeline:
    instances = 0

    def __init__(self, settings):
        FakePipeline.instances += 1

    def search(self, question, k=None):
        return CHUNKS[: k or 4]

    def ask(self, question, k=None):
        if question == "boom":
            raise LLMError("gemini rate limit or quota exceeded")
        if question == "unknown":
            return RagAnswer(question, NOT_FOUND_MESSAGE, [], CHUNKS)
        return RagAnswer(question, "60 days.", [CHUNKS[0]], CHUNKS)


def make_client(monkeypatch, tmp_path, **env) -> TestClient:
    monkeypatch.setattr(api, "RagPipeline", FakePipeline)
    settings = Settings.from_env(env={"AI_PROVIDER": "gemini", "GOOGLE_API_KEY": "test",
                                      "PDF_DIR": str(tmp_path), **env})
    return TestClient(api.create_app(lambda: settings))


@pytest.fixture
def client(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ask_returns_answer_and_sources(client):
    body = client.post("/ask", json={"question": "Notice period?"}).json()
    assert body["answer"] == "60 days."
    assert body["found"] is True
    assert body["sources"] == ["h.pdf, page 2"]
    assert body["chunks"] is None


def test_ask_can_include_retrieved_chunks(client):
    body = client.post("/ask", json={"question": "Notice period?", "include_chunks": True}).json()
    assert [c["reference"] for c in body["chunks"]] == ["h.pdf, page 2", "p.pdf, page 1"]
    assert body["chunks"][0]["text"] == "Notice period is 60 days."


def test_ask_not_found(client):
    body = client.post("/ask", json={"question": "unknown"}).json()
    assert body["found"] is False and body["sources"] == []


def test_ask_validates_input(client):
    assert client.post("/ask", json={"question": ""}).status_code == 422
    assert client.post("/ask", json={"question": "x", "k": 0}).status_code == 422


def test_provider_error_maps_to_502(client):
    r = client.post("/ask", json={"question": "boom"})
    assert r.status_code == 502
    assert "rate limit" in r.json()["detail"]


def test_database_error_maps_to_503(monkeypatch, client):
    def fail(_settings):
        raise DatabaseError("Cannot connect to PostgreSQL")

    monkeypatch.setattr(api, "get_status", fail)
    r = client.get("/status")
    assert r.status_code == 503 and "PostgreSQL" in r.json()["detail"]


def test_search(client):
    body = client.post("/search", json={"query": "notice", "k": 1}).json()
    assert len(body["chunks"]) == 1 and body["chunks"][0]["distance"] == 0.12


def test_upload_saves_pdf_and_lists_it(client, tmp_path):
    r = client.post("/documents", files={"file": ("My Policy (v2).pdf", b"%PDF-1.4 test", "application/pdf")})
    assert r.status_code == 201
    name = r.json()["filename"]
    assert name == "My_Policy_v2_.pdf"
    assert (tmp_path / name).read_bytes() == b"%PDF-1.4 test"
    assert client.get("/documents").json()["files"] == [name]


@pytest.mark.parametrize("filename,content", [("notes.txt", b"%PDF-1.4"), ("fake.pdf", b"hello"),
                                              ("../../evil.pdf", b"not a pdf")])
def test_upload_rejects_non_pdfs(client, tmp_path, filename, content):
    r = client.post("/documents", files={"file": (filename, content, "application/pdf")})
    assert r.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_upload_path_traversal_stays_in_pdf_dir(client, tmp_path):
    r = client.post("/documents", files={"file": ("../../evil.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 201
    assert [p.name for p in tmp_path.iterdir()] == ["evil.pdf"]


def test_upload_size_limit(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path, MAX_UPLOAD_MB="1") as c:
        r = c.post("/documents", files={"file": ("big.pdf", b"%PDF" + b"0" * (1024 * 1024), "application/pdf")})
    assert r.status_code == 413


def test_ingest_rebuilds_pipeline(monkeypatch, client):
    monkeypatch.setattr(api, "ingest", lambda s: IngestResult(files=["a.pdf"], pages=1, chunks=2))
    client.post("/ask", json={"question": "q"})
    before = FakePipeline.instances
    body = client.post("/ingest").json()
    assert body == {"files": ["a.pdf"], "pages": 1, "chunks": 2, "collection": "rag_documents"}
    client.post("/ask", json={"question": "q"})
    assert FakePipeline.instances == before + 1  # a fresh pipeline was opened after ingestion


def test_api_key_is_enforced_when_configured(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path, SERVICE_API_KEY="s3cret") as c:
        assert c.get("/health").status_code == 200  # health stays open for load balancers
        assert c.post("/ask", json={"question": "q"}).status_code == 401
        assert c.post("/ask", json={"question": "q"}, headers={"X-API-Key": "wrong"}).status_code == 401
        assert c.post("/ask", json={"question": "q"}, headers={"X-API-Key": "s3cret"}).status_code == 200
