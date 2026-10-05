# RAG Pipeline as a Service

`Cloud_AI_ML` · `AI-SEC` · `AI-OPS`

A working Retrieval-Augmented Generation (RAG) pipeline, run from the command line:

**PDF ingestion → Chunking → Embeddings → PostgreSQL/pgvector storage → Similarity search → LLM answer with sources**

Built with Python, LangChain, PostgreSQL and pgvector, with OpenAI or Google Gemini as the AI provider. It
ships with three synthetic sample PDFs and a ten-question evaluation set with automated accuracy scoring.

**AI provider:** during the testing phase the project runs on **Google Gemini** (low cost). **OpenAI** is fully
supported and is the planned production provider once the pipeline is mature. One setting (`AI_PROVIDER`)
switches both the embedding model and the chat model. See
[Switching between OpenAI and Gemini](#switching-between-openai-and-gemini).

> **Evaluation status:** **10/10 = 100%** (target ≥ 85%) on the three sample PDFs, measured with **Gemini** on
> 2026-09-30. OpenAI will be evaluated when the project moves to production.
> See [Evaluation results](#evaluation-results).

> **New to the project?** Start with **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**: a step-by-step
> guide to running the API and using it in your browser. No prior Python or Docker experience needed.

---

## Quickstart: a RAG chatbot for a new client

This repository is a template. An engineer can clone it, drop in a client's PDFs and have a working, evaluated
RAG API in about two hours. You need Docker Desktop and a Gemini API key.

```powershell
git clone https://github.com/trigitaltech/rag-pipeline-service.git client-name-rag
cd client-name-rag
Copy-Item .env.example .env          # then set GOOGLE_API_KEY in .env

# 1. Replace the sample PDFs with the client's documents (text-based PDFs, at least 3 by default)
Remove-Item data\pdfs\*.pdf
Copy-Item C:\path\to\client\*.pdf data\pdfs\

# 2. Start PostgreSQL + pgvector and the API, then build the index
docker compose up -d --build
docker compose exec api python -m rag_pipeline.cli ingest

# 3. Ask questions: open http://localhost:8000/docs (interactive), or:
Invoke-RestMethod http://localhost:8000/ask -Method Post -ContentType "application/json" `
  -Body '{"question": "What is the refund policy?"}'
```

Then make it the client's own:

| Step | What to do | Time |
|---|---|---|
| 4. Evaluation set | Write 10 questions with expected answers from the client's PDFs in `evaluation/questions.json` (keep one question that is *not* in the documents). Run `docker compose exec api python evaluation/evaluate.py`. Target ≥ 85%. | 45–60 min |
| 5. Tune if needed | If answers miss facts, try `CHUNK_SIZE=500`/`CHUNK_OVERLAP=100` or `TOP_K=6` in `.env`, then `docker compose up -d` and re-ingest. | 15–30 min |
| 6. Deploy | Follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for a free demo on Render + Neon, or GCP Cloud Run / AWS ECS for clients. | 30–60 min |

Without Docker, see [Setup (Windows, PowerShell)](#setup-windows-powershell) and run the API with
`uvicorn rag_pipeline.api:app --reload`.

## Features

- **PDF ingestion** of every PDF in `data/pdfs/`, keeping file name and page number for each page.
  Broken PDFs and PDFs with no text layer (scanned images) cause a clear error. They are never skipped silently.
- **Configurable chunking** (`CHUNK_SIZE`, `CHUNK_OVERLAP`) with LangChain's `RecursiveCharacterTextSplitter`.
- **Selectable provider and models**: `AI_PROVIDER` (`openai` or `gemini`), with the embedding model
  (`EMBEDDING_MODEL`) configured separately from the chat model (`LLM_MODEL`).
- **PostgreSQL + pgvector** storage via `langchain-postgres`. Re-running ingestion rebuilds only this
  project's collection and **never creates duplicates**.
- **Semantic similarity search** (cosine distance) with a configurable number of results (`TOP_K`).
- **Grounded answers**: the LLM may only use the retrieved excerpts. If the answer isn't there, it replies
  *"I could not find the answer in the provided documents."*
- **Source references** (file + page) for the excerpts the model says it used.
- **HTTP API (FastAPI)**: `/ask`, `/search`, `/ingest`, PDF upload, `/status`, `/health`, with interactive
  docs at `/docs` and optional API-key protection (`SERVICE_API_KEY`).
- **CLI** with `ingest`, `ask`, `chat` (interactive), `search` (retrieval only) and `status`.
- **Docker**: `Dockerfile` for the API and `docker-compose.yml` for the API + PostgreSQL/pgvector.
- **Deployment guide** for a free demo (Render + Neon), GCP Cloud Run and AWS ECS Fargate: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
- **Evaluation script**: runs 10 questions through the real pipeline, scores them, calculates accuracy
  and writes a report.
- **Tests**: 78 pytest tests (unit tests, API tests and a real-database integration test).

## Technology stack

| Purpose | Library / tool | Version |
|---|---|---|
| Language | Python | 3.11+ (verified on 3.14.7) |
| RAG workflow (prompt → LLM chain) | `langchain-core` | 1.6.5 |
| OpenAI embeddings + chat model (default) | `langchain-openai` / `openai` | 1.6.6 / 3.19.2 |
| Gemini embeddings + chat model (interim) | `langchain-google-genai` / `google-genai` | 4.4.0 / 2.25.0 |
| PDF loading | `langchain-community` (`PyPDFLoader`) + `pypdf` | 0.4.2 / 6.19.0 |
| Chunking | `langchain-text-splitters` | 1.1.2 |
| Vector store | `langchain-postgres` (`PGVector`) + `psycopg` 3 + SQLAlchemy | 0.0.18 / 3.3.6 / 2.1.1 |
| Database | PostgreSQL 16 + pgvector | pgvector 0.6+ |
| Config | `python-dotenv` | 1.2.3 |
| HTTP API | `fastapi` + `uvicorn` + `python-multipart` | 0.142.1 / 0.54.0 / 0.0.32 |
| Tests | `pytest` | 9.1.1 |

**Why `PGVector` rather than the newer `PGVectorStore`?** Both are in `langchain-postgres`, and `PGVector`
is not deprecated. `PGVector` uses synchronous psycopg, which is simple and reliable on Windows.
`PGVectorStore` runs an internal asyncio event loop, and async psycopg does not work with Windows' default
event loop.

## Architecture

```mermaid
flowchart LR
    subgraph Ingestion ["python -m rag_pipeline.cli ingest"]
        A[PDFs in data/pdfs] -->|PyPDFLoader| B[Pages + metadata<br/>source, page]
        B -->|RecursiveCharacterTextSplitter<br/>CHUNK_SIZE / CHUNK_OVERLAP| C[Chunks]
        C -->|OpenAI or Gemini embeddings<br/>AI_PROVIDER + EMBEDDING_MODEL| D[Vectors]
        D -->|PGVector| E[(PostgreSQL + pgvector<br/>collection rag_documents)]
    end
    subgraph Query ["python -m rag_pipeline.cli ask"]
        Q[Question] -->|same embedding model| QV[Query vector]
        QV -->|cosine similarity, TOP_K| E
        E --> R[Top-k chunks + sources]
        R --> P[Prompt: answer ONLY from context]
        P -->|chat model LLM_MODEL, temperature 0| ANS[Answer + file/page sources]
    end
```

## Project structure

```
rag-pipeline-service/
├── src/rag_pipeline/
│   ├── config.py        # settings from env/.env + validation (never prints the API key)
│   ├── ingestion.py     # PDF loading, metadata, empty/broken PDF detection
│   ├── chunking.py      # configurable RecursiveCharacterTextSplitter
│   ├── embeddings.py    # embeddings factory: OpenAI or Gemini (AI_PROVIDER, EMBEDDING_MODEL)
│   ├── vectorstore.py   # pgvector: enable extension, rebuild collection, status, open store
│   ├── retrieval.py     # similarity search + context formatting
│   ├── pipeline.py      # ingest() and RagPipeline.ask(): prompt, chat model, citations, error handling
│   ├── api.py           # HTTP API (FastAPI)
│   └── cli.py           # command-line interface
├── data/pdfs/           # 3 synthetic sample PDFs (fictional "Brightleaf Analytics")
├── evaluation/
│   ├── questions.json   # 10 questions, expected answers, sources, scoring criteria
│   ├── evaluate.py      # runs the questions through the real pipeline and scores them
│   └── results/         # eval_report.md + eval_results.json (created by evaluate.py)
├── scripts/
│   ├── make_sample_pdfs.py  # regenerates the sample PDFs
│   └── local_postgres.py    # Docker-free PostgreSQL + pgvector for Windows
├── docs/
│   ├── GETTING_STARTED.md   # first-day guide: start the API, use /docs in the browser
│   └── DEPLOYMENT.md        # deploying to Render + Neon (free) / GCP / AWS
├── tests/               # pytest suite
├── Dockerfile           # API container image
├── docker-compose.yml   # API + PostgreSQL 16 with pgvector
├── .env.example         # configuration template (copy to .env)
├── pyproject.toml       # package + pytest settings
└── requirements.txt     # pinned, verified dependency versions
```

## Prerequisites

- **Windows 10/11** (the commands below use PowerShell. They also work on macOS/Linux after adjusting paths)
- **Python 3.11 or newer**: check with `python --version`
- **PostgreSQL with pgvector**, either:
  - **Docker Desktop** (recommended), or
  - **no Docker**: the included `scripts/local_postgres.py` (Windows only; downloads about 20 MB)
- **An API key**: Google Gemini for testing (<https://aistudio.google.com/apikey>, free tier available), or
  OpenAI with available credits (<https://platform.openai.com/api-keys>)

## Setup (Windows, PowerShell)

Run every command from the project root folder (the folder that contains this README).

### 1. Create and activate a virtual environment

```powershell
cd D:\path\to\rag-pipeline-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell says running scripts is disabled, run this once and try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
When the venv is active, your prompt starts with `(.venv)`, and `python` refers to the project's interpreter.

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

`pip install -e .` registers the `src/rag_pipeline` package, so `python -m rag_pipeline.cli` works from the
project folder.

### 3. Start PostgreSQL with pgvector

**Option A: Docker (recommended)**

```powershell
docker compose up -d postgres
docker compose ps        # STATUS should be "healthy"
```

(`docker compose up -d --build` without `postgres` also builds and starts the API container. See
[HTTP API](#http-api).) This starts `pgvector/pgvector:pg16` on `localhost:5432` with user `postgres`, password `postgres` and
database `ragdb`. The data is kept in a Docker volume. Stop it with `docker compose down`.

To start the database with a single `docker run` instead, use the **pgvector image**. The plain `postgres:16`
image does not include pgvector, so ingestion would fail:

```powershell
docker run -d --name rag-postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ragdb `
  -p 5432:5432 -v rag-postgres-data:/var/lib/postgresql/data pgvector/pgvector:pg16
```

**Option B: no Docker (Windows)**

```powershell
python scripts/local_postgres.py setup    # first time: download, initialise, create ragdb, enable pgvector, start
python scripts/local_postgres.py start    # later sessions (e.g. after a reboot)
python scripts/local_postgres.py stop
python scripts/local_postgres.py status
```

This unpacks the official PostgreSQL 16 + pgvector build from the `pgserver` package on PyPI into
`.local-postgres/` (git-ignored). It doesn't install a Windows service or change any system settings.
It uses the same URL, user and password as Docker, so no configuration change is needed.

**Option C: an existing PostgreSQL server.** pgvector must be installed on the server. Set `DATABASE_URL` to
point at it. The pipeline runs `CREATE EXTENSION IF NOT EXISTS vector` itself.

### 4. Configure environment variables

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `GOOGLE_API_KEY=...` in `.env` (the template starts on Gemini; for OpenAI see below). **Never commit `.env`.** It is listed in `.gitignore`, and the
application never prints the key.

Check everything (this doesn't call the AI provider):

```powershell
python -m rag_pipeline.cli status
```

## Switching between OpenAI and Gemini

**Gemini** is used during the testing phase because it is cheaper. **OpenAI** is the planned production
provider. Everything else is identical for both providers: chunking, pgvector storage, retrieval, prompt,
evaluation and tests.

**Use Gemini** (in `.env`):

```ini
AI_PROVIDER=gemini
GOOGLE_API_KEY=your-gemini-key
EMBEDDING_MODEL=gemini-embedding-001
LLM_MODEL=gemini-2.5-flash          # or gemini-2.5-flash-lite / gemini-3.1-flash-lite (separate free quotas)
LLM_REQUESTS_PER_MINUTE=5           # stay under the free tier's per-minute limit
```

**Switch to OpenAI** (in `.env`):

```ini
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini
```

After switching, **always re-run ingestion and the evaluation**:

```powershell
python -m rag_pipeline.cli ingest
python evaluation/evaluate.py
```

Why re-ingest? Vectors from different embedding models aren't comparable (they even have different sizes:
1536 for `text-embedding-3-small`, 3072 for `gemini-embedding-001`). The collection records which model built
it, so if you forget, queries stop with a clear message instead of returning wrong results. A score measured
with Gemini is **not** an OpenAI score, and the evaluation report records which provider produced it.

If a model name doesn't match the provider (for example `gpt-4o-mini` with `AI_PROVIDER=gemini`), the
program stops with an error that names the correct setting.

## Usage

### Ingest the PDFs

```powershell
python -m rag_pipeline.cli ingest
```

This loads every PDF in `data/pdfs/`, splits the pages into chunks, embeds them with `EMBEDDING_MODEL` and
stores them in the pgvector collection `COLLECTION_NAME`. By default at least 3 PDFs are required
(`--min-docs N` changes this).

**Re-running is safe.** All chunks are embedded first. Only if that succeeds is this collection (and nothing
else in the database) replaced. You never get duplicates, and an API error never leaves you with an empty
index. **Re-run `ingest` whenever you change the PDFs, `CHUNK_SIZE`, `CHUNK_OVERLAP` or `EMBEDDING_MODEL`.**
If the embedding model in `.env` differs from the one the index was built with, queries refuse to run
and tell you to re-ingest.

### Ask questions

```powershell
python -m rag_pipeline.cli ask "What is the notice period after probation?"
python -m rag_pipeline.cli ask "Can I get a refund on an annual plan?" --show-chunks   # also print retrieved chunks
python -m rag_pipeline.cli ask "How much is the Growth plan?" -k 6                     # retrieve 6 chunks
python -m rag_pipeline.cli chat          # interactive: ask repeatedly, type 'exit' to quit
python -m rag_pipeline.cli search "sick leave"   # retrieval only (no LLM), shows chunks + distances
```

### HTTP API

Start the API, either locally (reads `.env`, uses the database from `DATABASE_URL`):

```powershell
uvicorn rag_pipeline.api:app --reload            # http://localhost:8000
```

or in Docker together with the database (`DATABASE_URL` is set to the `postgres` service automatically):

```powershell
docker compose up -d --build
docker compose exec api python -m rag_pipeline.cli ingest     # first time, or after changing PDFs
```

Open **<http://localhost:8000/docs>** for interactive documentation where you can try every endpoint in the
browser.

| Method and path | Body | Returns |
|---|---|---|
| `GET /health` | – | `{"status": "ok"}`. No database or AI calls; use it for load-balancer health checks. |
| `GET /status` | – | Provider, models, database version, and chunks per indexed PDF |
| `POST /ask` | `{"question": "...", "k": 4, "include_chunks": false}` | `answer`, `found`, `sources` (file + page), and optionally the retrieved `chunks` with text and distance |
| `POST /search` | `{"query": "...", "k": 4}` | Retrieved chunks only (no LLM call) |
| `GET /documents` | – | PDFs in `PDF_DIR` |
| `POST /documents` | multipart form field `file` (a PDF) | Saves it to `PDF_DIR`. Call `POST /ingest` afterwards. |
| `POST /ingest` | – | Rebuilds the index from every PDF in `PDF_DIR` |

```powershell
Invoke-RestMethod http://localhost:8000/ask -Method Post -ContentType "application/json" `
  -Body '{"question": "What is the notice period after probation?"}'
# answer : After an employee has completed probation, the notice period is 60 days.
# found  : True
# sources: {brightleaf_employee_handbook.pdf, page 2}

curl.exe -F "file=@C:\docs\policy.pdf" http://localhost:8000/documents
curl.exe -X POST http://localhost:8000/ingest
```

**Errors** return JSON `{"detail": "..."}` with the same message the CLI prints: `400` bad PDF, `401` wrong
API key, `413` file too large, `422` invalid request, `502` AI provider error (key, quota, model), `503`
database not reachable or index empty.

**Security:** if `SERVICE_API_KEY` is set, every endpoint except `/health` requires the header
`X-API-Key: <value>`. In `/docs`, click **Authorize** and paste the key. **Always set it when the API is
reachable from outside your machine.**

### Run the evaluation

```powershell
python evaluation/evaluate.py
```

This sends each of the 10 questions in `evaluation/questions.json` through the **real** pipeline (pgvector
retrieval + the configured provider's LLM, no mocks), scores every answer, prints the correct and incorrect counts and accuracy,
and writes:

- `evaluation/results/eval_report.md`: readable report with every answer, its sources and the scoring reason
- `evaluation/results/eval_results.json`: machine-readable results

The exit code is 0 if accuracy is at least 85%, otherwise 1.

### Run the tests

```powershell
python -m pytest -v
```

The unit tests need no API key. `tests/test_vectorstore_integration.py` runs against the real PostgreSQL
database, using a test-only word-hashing embedding in a throwaway collection so that it needs no API
credits. It is skipped if PostgreSQL isn't running. The unit tests don't prove the live OpenAI or Gemini integration
works; the evaluation run does that.

## Accuracy calculation

- There are 10 questions, each worth the same.
  **Accuracy = correct answers / 10.** The target of ≥ 85% therefore needs **at least 9/10** (8/10 = 80% fails).
- **Answerable questions (9):** each has `must_include` groups of required facts (for example `["24"], ["8", "eight"]`).
  An answer is correct only if it contains **every** group, and at least one alternative per group.
  Matching ignores case and requires whole numbers, so `12` does not match `120` or `99.12`. An answer
  of "not found" is always incorrect for these questions.
- **Unanswerable question (1):** Q10 asks for revenue, which isn't in any document. It is correct only if
  the pipeline replies with the not-found message, which tests that the system doesn't hallucinate.
- Retrieval quality (whether the expected source PDF was among the retrieved chunks) is reported separately
  and **not** counted in accuracy.
- Automated keyword scoring can miss correct paraphrases or accept a wrong answer that happens to contain the
  keywords, so the report shows every full answer for manual checking against the PDFs.

The questions cover all three documents: direct facts, prices and numbers, dates, a condition-based policy
question, reasoning over a table of ranges (98.5% uptime → which credit tier), a question that combines two
documents, and one unanswerable question.

## Evaluation results

All runs used the real pipeline (pgvector retrieval + live LLM, no mocks), chunk size/overlap 1000/200 and
`TOP_K=4`.

| Run | Chat model | Embedding model | Index | Automated result | Report |
|---|---|---|---|---|---|
| 2026-09-28 | `gemini-3.1-flash-lite` | `gemini-embedding-001` | 3 sample PDFs (8 chunks) | **10/10 = 100%** | [archived report](evaluation/results/2026-09-28_gemini-3.1-flash-lite_3-docs/eval_report.md) |
| 2026-09-30 (latest) | `gemini-2.5-flash-lite` | `gemini-embedding-001` | 3 sample PDFs (8 chunks) | **10/10 = 100%** | [eval_report.md](evaluation/results/eval_report.md) |
| OpenAI | `gpt-4o-mini` | `text-embedding-3-small` | – | planned for production | – |

- **Target ≥ 85% (≥ 9/10): met in both runs, with two different Gemini chat models.**
- **Retrieval:** in both runs, the expected source document was among the retrieved chunks for 9/9
  answerable questions.
- **Citations:** in the latest run, all 9 answerable questions cite the correct PDF and page.
- **Unanswerable question (Q10, revenue):** the pipeline correctly replied that it could not find the answer
  in both runs.
- An earlier attempt with `gemini-2.5-flash` is not counted: it hit the Gemini free tier's daily limit after
  5 questions. An incomplete run isn't a result.

**Manual verification (done separately from the automated scoring).** The answers were checked by hand against
the PDF text, and all are factually correct. One observation: Q6 (annual refund) correctly states the full
refund within 30 days but leaves out that the service stays active until the end of the term. Correct, but
incomplete.

Re-run at any time with:

```powershell
python -m rag_pipeline.cli ingest     # needed after changing provider, embedding model, chunking or PDFs
python evaluation/evaluate.py
```

## Sample output

Real output captured with the Gemini provider:

```text
> python -m rag_pipeline.cli ingest
Ingesting PDFs from D:\Trigital\rag-pipeline-service\data\pdfs
  chunk_size=1000 chunk_overlap=200 embedding_model=gemini-embedding-001
Done: 3 files, 6 pages, 8 chunks stored in collection 'rag_documents'.
  - brightleaf_company_profile.pdf
  - brightleaf_employee_handbook.pdf
  - brightleaf_support_and_refund_policy.pdf

> python -m rag_pipeline.cli ask "In which year and in which city was Brightleaf Analytics founded?"
Answer: Brightleaf Analytics was founded in March 2016 in Pune, India.
Sources:
  - brightleaf_company_profile.pdf, page 1

> python -m rag_pipeline.cli ask "What discount do customers get for annual billing?"
Answer: Customers who choose annual billing instead of monthly billing receive a 15% discount on the Starter and Growth plans.
Sources:
  - brightleaf_company_profile.pdf, page 2

> python -m rag_pipeline.cli ask "What is the capital of France?"
Answer: I could not find the answer in the provided documents.

> python evaluation/evaluate.py
[PASS] Q1: In which year and in which city was Brightleaf Analytics founded?
...
[PASS] Q10: What was Brightleaf Analytics' total revenue in 2024?
        answer: I could not find the answer in the provided documents.
============================================================
Correct:   10
Incorrect: 0
Accuracy:  10/10 = 100% (target >= 85%: PASSED)
```

The "capital of France" example shows the grounding rule working: the model knows the answer, but it isn't in
the documents, so the pipeline refuses to answer.

## Configuration options

All settings are environment variables, read from `.env` in the project root. Real environment variables
take precedence over `.env`.

| Variable | Default | Meaning |
|---|---|---|
| `AI_PROVIDER` | `openai` | `openai` or `gemini`. Selects the provider for both embeddings and answers. |
| `OPENAI_API_KEY` | *(required for openai)* | Your OpenAI key. Needed for `ingest`, `ask`, `chat`, `search` and the evaluation. |
| `GOOGLE_API_KEY` | *(required for gemini)* | Your Gemini key (`GEMINI_API_KEY` is also accepted). |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/ragdb` | SQLAlchemy URL for PostgreSQL (psycopg 3 driver). |
| `CHUNK_SIZE` | `1000` | Maximum characters per chunk. Must be > 0. |
| `CHUNK_OVERLAP` | `200` | Characters shared between neighbouring chunks. Must be ≥ 0 and < `CHUNK_SIZE`. |
| `EMBEDDING_MODEL` | `text-embedding-3-small` (openai) / `gemini-embedding-001` (gemini) | Embedding model (e.g. `text-embedding-3-large`). Re-ingest after changing. |
| `LLM_MODEL` | `gpt-4o-mini` (openai) / `gemini-2.5-flash` (gemini) | Chat model used to write answers (e.g. `gpt-4o`, `gemini-2.5-pro`). |
| `COLLECTION_NAME` | `rag_documents` | Name of the pgvector collection (a logical group of vectors). |
| `TOP_K` | `4` | Number of chunks retrieved per question (overridable per command with `-k`). |
| `LLM_REQUESTS_PER_MINUTE` | `0` (no limit) | Paces chat-model calls on the client side. Set `5` for the Gemini free tier. |
| `PDF_DIR` | `data/pdfs` | Folder containing the PDFs to ingest (relative to the project root). |
| `SERVICE_API_KEY` | *(empty = no auth)* | If set, the HTTP API requires the header `X-API-Key` with this value (except `/health`). |
| `MAX_UPLOAD_MB` | `20` | Maximum size of a PDF uploaded through `POST /documents`. |

**What chunk size and overlap mean.** An embedding represents one piece of text, and retrieval returns whole
pieces. So pages are cut into chunks of at most `CHUNK_SIZE` characters (the splitter prefers to cut at
paragraphs, then lines, then sentences). Smaller chunks give more precise matches but less context each.
Larger chunks carry more context but can dilute a match. `CHUNK_OVERLAP` repeats the last N characters of one
chunk at the start of the next, so a fact that falls on a boundary isn't cut in half.
**To change them:** edit `.env` (e.g. `CHUNK_SIZE=500`, `CHUNK_OVERLAP=100`) and re-run
`python -m rag_pipeline.cli ingest`. You can also set them for one PowerShell session only with
`$env:CHUNK_SIZE="500"`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `AI_PROVIDER is ... but ..._API_KEY is not set` | Set the key for the active provider in `.env`, with no quotes or spaces around it, and save the file. |
| `EMBEDDING_MODEL='...' is not a gemini model` (or openai) | The model names don't match `AI_PROVIDER`. Update both model lines when you switch provider. |
| `openai rejected the API key` / `gemini rejected the API key` | The key is wrong or revoked. Create a new one. |
| `rate limit or quota exceeded` | OpenAI: no credits, check Billing. Gemini free tier: per-minute limits, so wait a minute and re-run. |
| `model not found` | Your account can't use that `EMBEDDING_MODEL` / `LLM_MODEL`. Pick another. |
| `Cannot connect to PostgreSQL at DATABASE_URL` | Start the database: `docker compose up -d` or `python scripts/local_postgres.py start`. Check that port 5432 isn't used by another PostgreSQL. |
| `local_postgres.py status` says `not running` (after a reboot, or after the terminal that started it was killed) | Run `python scripts/local_postgres.py start` again. Your data is kept in `.local-postgres/data`. |
| `The pgvector extension is not available` | Your PostgreSQL doesn't have pgvector installed. Use the Docker image or `scripts/local_postgres.py`. |
| `Collection 'rag_documents' is empty or missing` | Run `python -m rag_pipeline.cli ingest` first. |
| `The collection was indexed with '...' but EMBEDDING_MODEL is '...'` | You changed the embedding model. Re-run `ingest`. |
| `No module named rag_pipeline` | Activate the venv and run `python -m pip install -e .` from the project root. |
| `ImportError: DLL load failed ... An Application Control policy has blocked this file` (SQLAlchemy) | Windows Smart App Control blocked SQLAlchemy's optional compiled speed-ups. Install its pure-Python wheel instead: `python -m pip download SQLAlchemy==2.1.1 --no-deps --platform any --only-binary=:all: -d wheels` then `python -m pip install --force-reinstall --no-deps (Get-ChildItem wheels\*.whl).FullName`. |
| `Activate.ps1 cannot be loaded because running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or skip activation and use `.\.venv\Scripts\python.exe` in place of `python`. |
| A PDF fails with `no extractable text` | The PDF is a scanned image. Run OCR on it first (for example, with Adobe Acrobat or `ocrmypdf`). |

## Known limitations

- **Evaluated on Gemini only so far.** Gemini is used during the testing phase to keep costs low. Before
  going to production with OpenAI, re-run ingestion and the evaluation with `AI_PROVIDER=openai`.
- **Gemini free tier limits.** The free tier allows only about 20 chat requests per day per model, plus a few
  per minute. `LLM_REQUESTS_PER_MINUTE` handles the per-minute limit. For the daily limit, wait for the reset,
  switch `LLM_MODEL` to another Gemini model, or enable billing.
- **Text-only PDFs.** There is no OCR, so scanned or image-only pages are rejected. Tables are extracted as
  plain text.
- **Full-collection rebuild on ingest.** This is simple and duplicate-free, but it re-embeds every chunk each
  time. That is fine for a handful of documents, but a large corpus would need incremental updates.
- **Keyword-based evaluation.** Scoring is transparent and deterministic but can't judge paraphrases. The
  report keeps full answers for manual review.
- **Small evaluation set.** 10 questions over 3 short synthetic documents. A high score here doesn't
  guarantee the same accuracy on large, messy real-world documents.
- **Answers vary slightly between runs.** Temperature is 0, but LLM output isn't strictly deterministic,
  so results can vary between runs.
- **Citations are what the model says it used.** They show where the supporting text should be, but they are
  not proof that the answer is correct. Check the page when it matters.
- **Single-tenant.** One collection per deployment, protected by one shared API key. There are no user
  accounts and no per-client isolation inside one deployment. Use one deployment (or one `COLLECTION_NAME`)
  per client.
- **Uploaded PDFs are stored on the container's disk.** On Cloud Run / Fargate that disk is temporary, so
  bake client PDFs into the image or re-upload them. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
- **No web chat UI yet.** Use `/docs` (Swagger UI), the CLI, or call the API from your own frontend.
- `scripts/local_postgres.py` is a Windows development convenience. Use Docker or a managed PostgreSQL
  for anything shared.
