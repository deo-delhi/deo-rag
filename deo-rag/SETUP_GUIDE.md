# DEO RAG Application Setup Guide

This guide gives an AI agent (or a human operator) everything needed to bring the
**DEO RAG System** up on a fresh machine — Windows or Linux/macOS — at any DEO
office. The system is a local, document-grounded question-answering app for
Defence Estates Organisation records.

The workspace layout is:

```text
RAGSYSTEM/                  # workspace root (this is where .venv lives)
├── .venv/                  # Python virtual environment (created by you, see Step 3)
└── deo-rag/                # the project itself
    ├── backend/            # FastAPI + LangChain + pgvector
    ├── frontend/           # React + Vite UI
    ├── documents/          # Data Library folders, one per `<library>/`
    ├── docker-compose.yml  # PostgreSQL + pgvector container
    ├── script.sh           # Linux/macOS launcher (bash)
    ├── script.ps1          # Windows launcher (PowerShell)
    ├── stop.sh / stop.ps1  # shutdown helpers
    ├── .env.example        # copy to .env and edit
    └── graphify-out/       # auto-generated knowledge graph (consult before edits)
```

## What This System Does

A user uploads PDFs into a **Data Library**, the backend parses, chunks and
embeds them into a per-library pgvector collection, and questions are answered
by retrieving the most relevant chunks and asking the local LLM to answer
strictly from those chunks. The UI then renders the answer with a
**Sources Referred** panel where each parent PDF is a clickable link that opens
the cited document in a new tab — using a **searchable sidecar PDF** when the
original was a scanned image.

Key DEO-specific features that are already implemented and that an agent must
not re-implement:

- **Data Libraries** — every knowledge base in the UI is shown as a "Data
  Library". The default catch-all library is named `unflagged`. The legacy
  name `default` is auto-migrated. Each library maps to its own pgvector
  collection (`deo_docs__<library_suffix>`).
- **Active vs Global query scope** — `/ask` accepts `query_scope: "active"` to
  search only the active library, or `"global"` to merge top-k chunks from
  every library before generating an answer.
- **Searchable sidecar PDFs** — during ingestion, scanned/low-text PDFs are
  detected (PyMuPDF text-length check). When OCR can run, an invisible-text
  overlay PDF is written to `documents/<library>/.searchable/<filename>` using
  PaddleOCR + PyMuPDF. Source links prefer the searchable copy so that office
  users get full text-search inside their PDF viewer; if OCR is unavailable
  the link gracefully falls back to the original PDF.
- **Sources Referred** — `/ask` returns sources grouped by parent file with
  `library`, `parent_source`, `pages[]`, `snippet`, `score`, and a
  `source_url` like `/sources/<library>/<filename>?searchable=true`. The
  backend exposes `GET /sources/{library}/{filename}` with path-traversal
  validation and `FileResponse` so the UI can link to the PDF directly.
- **DEO-grounded prompts** — both the main and fallback prompts say
  *"You are a Defence Estates Organisation records assistant"* and refuse to
  give legal/financial/title/administrative conclusions unless the context
  directly supports them.

If anything below contradicts the actual code, **the code wins**. Read
`graphify-out/GRAPH_REPORT.md` first to find the right files to edit.

---

## Prerequisites

| Component | Minimum version | Notes |
|---|---|---|
| Python | 3.10+ (3.11 or 3.13 work) | `py` on Windows, `python3` on Linux/macOS |
| Node.js | 18 LTS or newer | brings `npm`. Vite 5 needs Node 18+ |
| Docker Desktop / Docker Engine | recent | Docker Compose v2 plugin (`docker compose ...`) |
| Ollama | 0.3+ | for local LLM and (optional) embeddings |
| Disk space | ~15 GB free | torch + sentence-transformers + paddle + ollama models |
| GPU (optional) | NVIDIA + CUDA 12.1 | speeds up embeddings, not required |

### Check what is already on the machine

**Windows (PowerShell):**

```powershell
py --version
node --version
npm --version
docker --version
docker compose version
ollama --version
```

**Linux/macOS:**

```bash
python3 --version
node --version
npm --version
docker --version
docker compose version
ollama --version
```

If `npm --version` errors but `node` works, install real Node.js — Cursor and
some editors ship a private `node.exe` that is not a full Node distribution.
On Windows the easiest install is `winget install OpenJS.NodeJS.LTS`. On
Debian/Ubuntu use the official NodeSource repo.

---

## Step 1 — Get the source

```powershell
# Windows
cd C:\path\to\workspace
# (clone or copy the project so it lands at <workspace>\deo-rag\)
```

```bash
# Linux / macOS
cd /path/to/workspace
# (clone or copy the project so it lands at <workspace>/deo-rag/)
```

The rest of this guide assumes your shell is **inside `deo-rag/`** unless
explicitly stated otherwise.

## Step 2 — Configure the environment file

Inside `deo-rag/`:

**Windows:**

```powershell
Copy-Item .env.example .env
```

**Linux/macOS:**

```bash
cp .env.example .env
```

Open the new `.env` and fill in/adjust:

- `LLM_PROVIDER` — `ollama` (default) or `openai`.
- `LLM_MODEL` — the Ollama model tag, e.g. `llama3.2:latest` or `llama3.2:1b`
  for very small machines.
- `EMBEDDING_PROVIDER` — `ollama`, `huggingface`, or `openai`.
- `EMBEDDING_MODEL` — for Ollama use `mxbai-embed-large:latest` or
  `nomic-embed-text:latest`; for HF use `BAAI/bge-small-en`.
- `OLLAMA_BASE_URL` — usually `http://localhost:11434`.
- `DATABASE_URL` — keep the default
  `postgresql+psycopg2://admin:admin123@localhost:5202/deorag` if you are using
  the bundled docker compose stack.
- `COLLECTION_NAME` — base name for the pgvector tables, default `deo_docs`.
- `LANGCHAIN_PROJECT=deo-rag` — for LangSmith tracing if you turn it on.
- **`ALLOWED_ORIGINS`** — comma-separated list of origins that the React
  frontend will be served from at this office. The defaults already cover
  `http://localhost:5201` and `http://127.0.0.1:5201`; add the LAN URL the
  office actually uses. Example:

  ```env
  ALLOWED_ORIGINS=http://localhost:5201,http://127.0.0.1:5201,http://10.20.30.40:5201
  ```

- **`ALLOWED_ORIGIN_REGEX`** — optional; use this if the office serves the
  frontend from a dynamic LAN range. Example for any host on a `/16`:

  ```env
  ALLOWED_ORIGIN_REGEX=^http://192\.168\.\d+\.\d+:5201$
  ```

If both `ALLOWED_ORIGINS` and `ALLOWED_ORIGIN_REGEX` are set, FastAPI accepts
either match. **Do not** hardcode IPs in `backend/app.py` — CORS is now driven
entirely from these two env vars.

## Step 3 — Create the Python virtual environment

The launcher scripts expect the venv at the **workspace root** (one level
above `deo-rag/`). That is, at `<workspace>/.venv/`. This keeps the heavy ML
dependencies out of the project folder.

**Windows (PowerShell), from inside `deo-rag/`:**

```powershell
py -m venv ..\.venv
..\.venv\Scripts\python -m pip install --upgrade pip
..\.venv\Scripts\python -m pip install -r backend\requirements.txt
```

**Linux/macOS, from inside `deo-rag/`:**

```bash
python3 -m venv ../.venv
../.venv/bin/python -m pip install --upgrade pip
../.venv/bin/python -m pip install -r backend/requirements.txt
```

`backend/requirements.txt` pins:

- FastAPI + Uvicorn for the HTTP layer
- LangChain (classic + community + text-splitters), LangGraph, LangSmith
- `psycopg2-binary`, `pgvector`, `sqlalchemy` for the vector store
- `pypdf`, `pymupdf`, `unstructured[all-docs]`, `docling` for PDF parsing
- `paddleocr` and `paddlepaddle` for sidecar searchable-PDF generation
- `sentence-transformers`, `rank-bm25`, `tiktoken`, `openai`, `langchain-ollama`

The first install pulls **several gigabytes** (torch, paddle, sentence
encoders). Allow 10–30 minutes on a normal connection.

### Optional GPU acceleration

If the host has an NVIDIA GPU with CUDA 12.x, replace the bundled CPU torch
build with a CUDA build *after* the bulk install:

```powershell
# CUDA 12.1
..\.venv\Scripts\python -m pip install --upgrade --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
..\.venv\Scripts\python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

This is **not required**. The system runs end-to-end on CPU; GPU only speeds
up HuggingFace embeddings.

### Optional CPU fallback when paddle wheels fail

`paddlepaddle` and `paddleocr` are only used when ingesting scanned PDFs. The
parser already wraps the `import paddleocr` in a try/except, so if the wheel
fails to install on a particular Windows machine you can:

```powershell
..\.venv\Scripts\python -m pip install -r backend\requirements.txt --no-deps
..\.venv\Scripts\python -m pip install -r backend\requirements.txt
# or, more aggressively, comment out paddlepaddle/paddleocr in requirements.txt
```

When OCR is unavailable, scanned PDFs simply fall back to the original PDF in
the Sources Referred panel — no error, just no in-PDF text search.

## Step 4 — Pull the Ollama models

Make sure the Ollama service is running:

**Windows:**

```powershell
# Start the Ollama background service if it isn't already
Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
# wait a couple of seconds then check
ollama list
```

**Linux:** `systemctl --user start ollama` (or run `ollama serve` in a tmux).

**macOS:** start Ollama.app or run `ollama serve` in a terminal.

Then pull whatever you set in `.env`:

```powershell
ollama pull llama3.2:latest
ollama pull mxbai-embed-large:latest   # only if EMBEDDING_PROVIDER=ollama
```

Smaller machines:

```powershell
ollama pull llama3.2:1b
ollama pull nomic-embed-text:latest
```

Verify:

```powershell
curl http://localhost:11434/api/tags
```

## Step 5 — Start PostgreSQL + pgvector (and verify)

From inside `deo-rag/`:

```powershell
docker compose up -d postgres
docker compose ps postgres
docker compose exec -T postgres pg_isready -U admin -d deorag
```

The container is named `deo_pgvector` and listens on host port `5202`. The
database name is `deorag` and the default credentials match `.env.example`.

## Step 6 — Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

This installs Vite 5 + React 18 + react-markdown. The frontend's
`package.json` is named `deo-rag-frontend`.

## Step 7 — Start the full stack

You have three options. Pick whichever the office prefers.

### Option A — One-shot launcher (recommended)

**Windows (PowerShell), from inside `deo-rag/`:**

```powershell
.\script.ps1
```

**Linux/macOS, from inside `deo-rag/`:**

```bash
VENV_PY="$(pwd)/../.venv/bin/python" ./script.sh
```

Both launchers:

1. ensure the three ports (5200/5201/5202) are free
2. start `postgres` via docker compose and wait for `pg_isready`
3. start `uvicorn backend.app:app` on port 5200
4. start `npm run dev -- --port 5201` on port 5201
5. wait until `/health` and the frontend dev server respond

Logs go to `.run-logs/backend.log` and `.run-logs/frontend.log`.

### Option B — Run components manually (good for debugging)

Open three terminals.

Terminal 1 — Postgres:

```powershell
cd deo-rag
docker compose up postgres
```

Terminal 2 — backend:

```powershell
cd deo-rag
..\.venv\Scripts\python -m uvicorn backend.app:app --host 0.0.0.0 --port 5200 --app-dir .
```

Terminal 3 — frontend:

```powershell
cd deo-rag\frontend
npm run dev -- --host 0.0.0.0 --port 5201
```

### Option C — Pure docker compose (no host venv)

`docker-compose.yml` already has a `backend` service. You'll still need to
build it the first time:

```powershell
cd deo-rag
docker compose up -d --build
```

This does **not** start the frontend dev server; you would still need
`npm run dev` (or `npm run build` + serve `dist/`) on the host or in another
container.

## Step 8 — Smoke test

Once everything is up:

```powershell
curl http://localhost:5200/health
curl http://localhost:5200/settings
curl http://localhost:5200/knowledge-bases
```

Open the UI:

- **Frontend UI:** `http://localhost:5201`
- **Backend OpenAPI docs:** `http://localhost:5200/docs`

End-to-end check:

1. In the UI, leave the active Data Library as `unflagged` (or create a new
   one) and upload a PDF.
2. Click **Start ingestion** and wait for `completed`.
3. Switch the **Query scope** between *Active library only* and
   *Global search across all libraries*.
4. Ask a question. Confirm the answer renders and that **Sources Referred**
   shows clickable parent-PDF links.
5. Click a source link — it should open the cited PDF in a new tab. For a
   scanned PDF, you should be able to use the PDF viewer's text-find inside
   the document (that proves the searchable sidecar was created).
6. Try a path-traversal URL manually, e.g.
   `http://localhost:5200/sources/unflagged/..%2Fapp.py` — it must respond
   `400 Invalid source filename` or `400 Invalid source path`.

## Step 9 — Keep the knowledge graph in sync

This project ships a Graphify knowledge graph at `deo-rag/graphify-out/`. AI
agents are expected to consult it before reading raw files.

After **code** changes (AST-only, free):

```powershell
py -m graphify update deo-rag
```

After **doc / markdown / image** changes (needs an LLM key, has small token
cost):

```text
/graphify deo-rag --update    # invoke as a Cursor slash command
```

Both are no-ops if nothing changed.

## Shutdown

**Windows:**

```powershell
.\stop.ps1
```

**Linux/macOS:**

```bash
./stop.sh
```

Both stop the backend, the frontend dev server, and `docker compose down`
the Postgres container.

## Troubleshooting

### `npm` not found but `node` works

You probably have the editor's bundled `node.exe`, not a real Node.js.
Install Node.js LTS — on Windows: `winget install OpenJS.NodeJS.LTS`, then
open a new shell.

### Backend boots but `/ask` returns 500

Almost always a missing Ollama model or Ollama not running. Verify with
`ollama list` and re-pull the model named in `.env`'s `LLM_MODEL`. Also check
`OLLAMA_REQUEST_TIMEOUT_SECONDS` — slow local machines benefit from `120` or
`180`.

### `Collection not found` after a clear

Already handled in code — `backend/ingest.py` calls
`vectorstore.create_collection()` before indexing so a clear+re-ingest cycle
works. If you still see this, you are talking to a stale backend; restart it.

### `Cannot clear data while ingestion is running` (HTTP 409)

That is intentional — the clear endpoint refuses while a background ingest
job for the same Data Library is `running`. Wait for the job to finish or
restart the backend.

### CORS error in the browser

Add the actual frontend origin (e.g. `http://10.20.30.40:5201`) to
`ALLOWED_ORIGINS` in `.env` and restart the backend. Or use
`ALLOWED_ORIGIN_REGEX` for a whole subnet.

### `paddlepaddle` / `paddleocr` install fails on Windows

Skip them — see the *CPU fallback* note in Step 3. The system still works
end-to-end for native-text PDFs; only the searchable sidecar feature for
scanned PDFs is disabled.

### Port already in use

```powershell
# Windows
Get-NetTCPConnection -State Listen -LocalPort 5200,5201,5202 |
  Select-Object LocalPort,OwningProcess
Stop-Process -Id <pid> -Force
```

```bash
# Linux/macOS
lsof -ti:5200,5201,5202 | xargs -r kill -9
docker compose down
```

### Re-ingest is slow

The default chunk batch size is 1 (intentional, for progress UX). Bump
`OLLAMA_NUM_CTX` and `OLLAMA_NUM_PREDICT` in `.env` if your host can spare
RAM, and consider switching `EMBEDDING_PROVIDER` to `huggingface` with GPU.

## Key Configuration Files

| File | Purpose |
|---|---|
| `.env` | runtime configuration (LLM, embeddings, DB, CORS, timeouts) |
| `.env.example` | template; copy to `.env` |
| `backend/requirements.txt` | Python dependencies |
| `backend/config.py` | reads `.env` into a frozen `Settings` dataclass |
| `backend/app.py` | FastAPI routes, CORS (env-driven), ingest state machine |
| `backend/rag_pipeline.py` | DEO-grounded prompts + retriever wiring |
| `backend/parser.py` | Docling → PyPDF fallback + searchable sidecar OCR |
| `backend/ingest.py` | parse → chunk → embed pipeline with progress |
| `frontend/src/App.jsx` | UI: Data Libraries, query scope, Sources Referred |
| `docker-compose.yml` | `deo_pgvector` (pg16+pgvector) + optional backend |
| `script.sh` / `script.ps1` | one-shot launchers |
| `stop.sh` / `stop.ps1` | shutdown helpers |
| `graphify-out/GRAPH_REPORT.md` | knowledge-graph entry point for agents |

## Application URLs (defaults)

- **Frontend UI**: http://localhost:5201
- **Backend API**: http://localhost:5200
- **API Docs (Swagger)**: http://localhost:5200/docs
- **Postgres (pgvector)**: `localhost:5202`, db `deorag`, user/pass `admin/admin123`

Replace `localhost` with the office's LAN hostname/IP when the stack is bound
to `0.0.0.0` (the launchers do this by default), and remember to add that
hostname to `ALLOWED_ORIGINS` in `.env`.

## Logs

- `.run-logs/backend.log`
- `.run-logs/frontend.log`

Tail them while ingesting to watch chunk-batch progress and OCR/sidecar
generation messages.
