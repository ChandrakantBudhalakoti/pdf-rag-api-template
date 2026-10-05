# Getting started: run the API and use it in your browser

This guide is for your **first day** on the project. It assumes no experience with Python, Docker or RAG.
Follow the steps in order. After each step there is a **✅ Check** that tells you what you should see.
If the check fails, stop and look at [When something goes wrong](#when-something-goes-wrong).

**What this project does, in one sentence:** you give it PDFs, it reads and indexes them, and then you can ask
questions and get answers taken **only** from those PDFs, with the file name and page number as the source.

**Time needed:** about 30 minutes the first time, and 1 minute on later days.

---

## Step 0: What you need

| You need | How to check (in PowerShell) | If it's missing |
|---|---|---|
| **Git** | `git --version` | Install from <https://git-scm.com> |
| **Docker Desktop**, running | `docker info` shows no error | Install from <https://www.docker.com/products/docker-desktop>, then start it from the Start menu and wait until it says *Engine running* |
| **A Gemini API key** | – | Ask your team lead, or create one (free) at <https://aistudio.google.com/apikey> |

All commands below are typed in **PowerShell** (Start menu → type *PowerShell*).

> **Never share the API key** in chat, email or a git commit. It only goes into the `.env` file, which git
> ignores.

---

## Step 1: Get the code

```powershell
cd D:\                       # or any folder where you keep projects
git clone https://github.com/trigitaltech/rag-pipeline-service.git
cd rag-pipeline-service
```

✅ **Check:** `ls` shows `README.md`, `Dockerfile`, `docker-compose.yml`, `src`, `data` and more.

---

## Step 2: Add your settings (`.env` file)

```powershell
Copy-Item .env.example .env
notepad .env
```

In Notepad, find this line and paste your key after the `=` sign (no spaces, no quotes):

```ini
GOOGLE_API_KEY=AIzaSy...your-key...
```

Save and close Notepad. Leave everything else as it is.

✅ **Check:** `Select-String GOOGLE_API_KEY .env` shows your key on the line (not an empty value).

---

## Step 3: Start the API and the database

```powershell
docker compose up -d --build
```

The first run downloads and builds everything and takes **3–5 minutes**. Later runs take seconds.
This starts two containers:

- `rag-pgvector`: the database (PostgreSQL with pgvector), where the indexed documents are stored
- `rag-api`: the API server, on port **8000**

✅ **Check:**

```powershell
docker compose ps
```

Both rows should say **`Up`** and **`(healthy)`**. The API can take up to 30 seconds to become healthy.
Then open **<http://localhost:8000/health>** in your browser. It should show `{"status":"ok"}`.

---

## Step 4: Index the documents (first time only)

The project ships with 3 sample PDFs about a fictional company, *Brightleaf Analytics*, in `data/pdfs/`.
Before you can ask questions, they must be **ingested**: read, cut into chunks, converted to vectors and
stored in the database.

```powershell
docker compose exec api python -m rag_pipeline.cli ingest
```

✅ **Check:** the output ends like this:

```text
Done: 3 files, 6 pages, 8 chunks stored in collection 'rag_documents'.
  - brightleaf_company_profile.pdf
  - brightleaf_employee_handbook.pdf
  - brightleaf_support_and_refund_policy.pdf
```

The index is saved in the database, so you **don't** need to do this again after a restart. Only re-run it
when the PDFs change.

---

## Step 5: Open the API docs in your browser

Open **<http://localhost:8000/docs>**

This is **Swagger UI**, an interactive page that FastAPI generates automatically. It lists every endpoint
(every "URL you can call") and lets you try each one without writing any code.

You'll see three groups:

| Group | Endpoints | What they're for |
|---|---|---|
| **service** | `GET /health`, `GET /status` | Is the server alive? What's in the index? |
| **documents** | `GET /documents`, `POST /documents`, `POST /ingest` | See, upload and index PDFs |
| **query** | `POST /search`, `POST /ask` | Ask questions |

### How to try any endpoint (the same 4 clicks every time)

1. Click the endpoint's row, for example the green **`POST /ask`**, to expand it.
2. Click **Try it out** (on the right).
3. Edit the example in the **Request body** box, if there is one.
4. Click the blue **Execute** button, then scroll down to **Responses**.
   - **Code** `200` or `201` means success. The **Response body** shows the result.
   - Anything else is an error, and the body explains what went wrong.

---

## Step 6: Ask your first question

In `/docs`, open **`POST /ask`** → **Try it out**, replace the request body with:

```json
{
  "question": "What is the notice period after probation?",
  "include_chunks": true
}
```

Click **Execute**.

✅ **Check:** code **200** and a response body like this:

```json
{
  "question": "What is the notice period after probation?",
  "answer": "After an employee has completed probation, the notice period is 60 days.",
  "found": true,
  "sources": ["brightleaf_employee_handbook.pdf, page 2"],
  "chunks": [
    { "reference": "brightleaf_employee_handbook.pdf, page 2", "distance": 0.2823, "text": "..." },
    ...
  ]
}
```

**How to read the answer:**

| Field | Meaning |
|---|---|
| `answer` | The answer, written by the AI using **only** the PDF text |
| `found` | `false` means the answer isn't in the documents. The AI says so instead of guessing. |
| `sources` | Which PDF and page the answer came from. Open the PDF and check! |
| `chunks` | *(only with `"include_chunks": true`)* The pieces of PDF text the search found, closest first. This is exactly what the AI was given to read. `distance` near 0 = very relevant; around 0.5 or more = weak match. |
| `k` *(in the request, optional)* | How many chunks to retrieve. The default is 4. |

**Try a question that is not in the documents**, for example `"What is the capital of France?"`. You should
get `"found": false` and *"I could not find the answer in the provided documents."* That's correct: the
system refuses to answer from general knowledge.

**`POST /search`** does the same search but **without** the AI. It's useful for checking that the right text
is being found. It's also free and fast, so use it while experimenting.

---

## Step 7: Add your own PDF

1. In `/docs`, open **`POST /documents`** → **Try it out** → **Choose File** → pick a PDF → **Execute**.
   You should get code **201**, with `"message": "Saved. Call POST /ingest to add it to the index."`
2. Open **`POST /ingest`** → **Try it out** → **Execute**. You should get code **200**, and your file is listed
   in `files`.
3. Ask a question about your PDF with `POST /ask`.

Notes:

- Uploaded files are saved in the project's `data/pdfs/` folder on your computer. You can also just copy PDFs
  into that folder and call `POST /ingest`.
- Only PDFs with real text work. A scanned PDF (a photo of paper) is rejected with a clear message.
- Ingestion rebuilds the whole index from **all** PDFs in `data/pdfs/`. To remove a document, delete the file
  and ingest again.

---

## Step 8: Stop, and start again tomorrow

```powershell
docker compose stop        # stop (your index is kept)
docker compose start       # start again later, then open http://localhost:8000/docs
```

After changing **code** (anything in `src/`), rebuild: `docker compose up -d --build`.
After changing **`.env`**, recreate: `docker compose up -d`.

`docker compose down -v` deletes the containers **and the index**. You would need to run Step 4 again.

---

## Other ways to call the API

The browser page is the easiest, but the same requests work from anywhere.

**PowerShell:**

```powershell
Invoke-RestMethod http://localhost:8000/ask -Method Post -ContentType "application/json" `
  -Body '{"question": "How much does the Growth plan cost?"}'
```

**curl** (use `curl.exe` in PowerShell, because plain `curl` is a different command there):

```powershell
curl.exe -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{\"question\": \"How much does the Growth plan cost?\"}'
curl.exe -F "file=@C:\path\to\document.pdf" http://localhost:8000/documents
```

**JavaScript (a frontend):**

```js
const res = await fetch("http://localhost:8000/ask", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: "How much does the Growth plan cost?" }),
});
const { answer, sources } = await res.json();
```

---

## If the API asks for a key (`401`)

If `SERVICE_API_KEY` is set in `.env`, the API is locked, and every call except `/health` returns **401**.
In `/docs`, click the **Authorize** button (top right, with a lock icon), paste the key, click **Authorize**,
then **Close**. Swagger now sends it with every request. From code, send the header `X-API-Key: <the key>`.

On your own computer you can leave `SERVICE_API_KEY` empty. **On any server reachable from the internet, it
must be set.**

---

## Running without Docker (optional)

Use this if you can't use Docker, or you want to change the Python code with instant reloads.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1               # your prompt now starts with (.venv)
python -m pip install -r requirements.txt
python -m pip install -e .

python scripts/local_postgres.py setup     # first time: downloads a local database (Windows only)
# on later days:  python scripts/local_postgres.py start

python -m rag_pipeline.cli ingest          # same as Step 4
uvicorn rag_pipeline.api:app --reload      # start the API
```

✅ **Check:** the last command prints `Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)` and
`Application startup complete.` Now open <http://localhost:8000/docs> exactly as in Step 5.
`--reload` restarts the server automatically when you save a code file. Press **Ctrl+C** to stop it.

Use **either** Docker **or** `local_postgres.py`, not both at once: they both use port 5432.

---

## When something goes wrong

| What you see | What it means | Fix |
|---|---|---|
| `docker: ... cannot find the file specified` / `failed to connect to the docker API` | Docker Desktop isn't running | Start Docker Desktop and wait for *Engine running* |
| `Bind for 0.0.0.0:5432 failed: port is already allocated` | Another database is using port 5432 (often `local_postgres.py`) | `python scripts/local_postgres.py stop`, then `docker compose up -d` |
| Port 8000 already in use | Another API copy is running | Stop the other one (Ctrl+C in its window, or `docker compose stop`) |
| <http://localhost:8000/docs> doesn't load | The API isn't running (yet) | `docker compose ps`. If `rag-api` isn't `Up`, run `docker compose logs api` and read the last lines |
| **503** `Collection 'rag_documents' is empty or missing` | Nothing ingested yet | Do Step 4 |
| **503** `Cannot connect to PostgreSQL` | The database isn't running | `docker compose up -d` |
| **502** `... rate limit or quota exceeded` | Gemini's free tier limit (about 20 questions per day per model, plus a few per minute) | Wait a minute. If it keeps happening, the daily quota is used up: change `LLM_MODEL` in `.env` to `gemini-3.1-flash-lite` (separate quota), then `docker compose up -d` |
| **502** `... rejected the API key` | Wrong or missing key | Fix `GOOGLE_API_KEY` in `.env`, then `docker compose up -d` |
| **500** `AI_PROVIDER is gemini but GOOGLE_API_KEY is not set` | `.env` has no key, or wasn't saved | Step 2 again, then `docker compose up -d` |
| **400** `no extractable text` | The PDF is a scanned image | Use a text PDF, or OCR it first |
| **401** `Missing or invalid X-API-Key header` | The API is locked | See [If the API asks for a key](#if-the-api-asks-for-a-key-401) |
| **422** | The request body is wrong (for example, an empty question) | Read the `detail` in the response. It names the field. |

Still stuck? Run `docker compose logs api --tail 50` and share the output with the team. The application
never prints your API key, but glance over the output before sharing it anyway.

---

## Where to go next

- [README.md](../README.md): how the pipeline works, all configuration options, and the evaluation
- `python evaluation/evaluate.py` (or `docker compose exec api python evaluation/evaluate.py`): runs the
  10 test questions and scores the accuracy
- [DEPLOYMENT.md](DEPLOYMENT.md): putting the API online: free on Render + Neon, or on GCP or AWS
