# Agent Prompt — DEO RAG Offline Desktop Application

> **Purpose:** Hand this file to your coding agent (Claude Code, Cursor, Copilot Workspace, etc.) as the complete specification to build the application from scratch. The agent should read this entire document before writing a single line of code.

---

## 0. Mission Statement

Build a **fully offline, self-contained DEO record question-answering system** that can be distributed via USB pendrive to end users running Ubuntu. The system uses Retrieval-Augmented Generation (RAG) — users upload DEO PDF documents, the system ingests and indexes them, and users can ask plain-language questions and receive answers grounded only in those documents.

The deliverable is a folder (`myapp-installer/`) that can be copied to a pendrive and installed on any Ubuntu machine by running a single shell script.

---

## 1. Tech Stack (Non-Negotiable)

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React (Vite) | Built to static `dist/` and served by FastAPI |
| Backend | FastAPI (Python 3.11) | Handles all API routes, serves frontend, runs background jobs |
| Vector DB | PostgreSQL 16 + pgvector | Use `pgvector/pgvector:pg16` Docker image |
| LLM + Embeddings | Ollama | Runs inside Docker, models pre-loaded at install time |
| Embedding model | `nomic-embed-text` via Ollama | Pull at install time |
| LLM model | `llama3` via Ollama | Pull at install time |
| PDF parsing | `pdfplumber` (primary), `pypdf` (fallback) | Always try pdfplumber first |
| Containerisation | Docker + Docker Compose | All 3 services in one compose file |
| Installer | Bash scripts | `install.sh`, `start.sh`, `stop.sh` |

---

## 2. Repository Structure

Create exactly this folder and file structure. Do not deviate:

```
myapp-installer/
│
├── docker-compose.yml
├── install.sh
├── start.sh
├── stop.sh
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── documents.py       # Upload, ingest, list, delete
│   │   ├── ask.py             # Question answering
│   │   └── debug.py           # Retrieval debug endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── parser.py          # PDF parsing (pdfplumber + pypdf fallback)
│   │   ├── chunker.py         # Text chunking logic
│   │   ├── embedder.py        # Ollama embedding calls
│   │   ├── retriever.py       # Vector similarity search
│   │   ├── generator.py       # LLM answer generation
│   │   └── ingestion.py       # Background ingestion pipeline
│   │
│   └── frontend/              # React build copied here at Docker build time
│       └── dist/              # (populated by frontend build step)
│
├── frontend/
│   ├── Dockerfile             # Only used for building, not running
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── components/
│           ├── UploadPanel.jsx
│           ├── QuestionPanel.jsx
│           ├── AnswerDisplay.jsx
│           ├── DocumentList.jsx
│           └── StatusBar.jsx
│
├── images/                    # Docker image tars (populated by build script)
│   └── .gitkeep
│
├── models/                    # Ollama model blobs (populated by build script)
│   └── .gitkeep
│
└── scripts/
    └── build-distribution.sh  # Run on developer machine to prepare pendrive
```

---

## 3. Docker Compose — Full Specification

### `docker-compose.yml`

```yaml
version: "3.9"

services:
  backend:
    image: myapp_backend:latest
    container_name: myapp_backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://myapp:myapp@db:5432/myapp
      - OLLAMA_URL=http://ollama:11434
      - OLLAMA_EMBED_MODEL=nomic-embed-text
      - OLLAMA_LLM_MODEL=llama3
      - UPLOAD_DIR=/app/uploads
      - CHUNK_SIZE=512
      - CHUNK_OVERLAP=64
      - TOP_K=5
      - SIMILARITY_THRESHOLD=0.3
      - MAX_TOKENS=768
      - MAX_TOKENS_FALLBACK=1024
    volumes:
      - uploads:/app/uploads
    depends_on:
      db:
        condition: service_healthy
      ollama:
        condition: service_started
    restart: unless-stopped
    networks:
      - myapp_network

  db:
    image: pgvector/pgvector:pg16
    container_name: myapp_db
    environment:
      - POSTGRES_USER=myapp
      - POSTGRES_PASSWORD=myapp
      - POSTGRES_DB=myapp
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myapp"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped
    networks:
      - myapp_network

  ollama:
    image: ollama/ollama:latest
    container_name: myapp_ollama
    volumes:
      - ollama_models:/root/.ollama
    restart: unless-stopped
    networks:
      - myapp_network

volumes:
  postgres_data:
  ollama_models:
  uploads:

networks:
  myapp_network:
    driver: bridge
```

---

## 4. Backend — Full Specification

### 4.1 `backend/requirements.txt`

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
pgvector==0.2.5
pdfplumber==0.11.0
pypdf==4.2.0
httpx==0.27.0
python-multipart==0.0.9
aiofiles==23.2.1
pydantic-settings==2.2.1
tenacity==8.3.0
```

### 4.2 `backend/config.py`

Use `pydantic-settings` to load all configuration from environment variables. Every value must have a default that works for local development. Fields: `DATABASE_URL`, `OLLAMA_URL`, `OLLAMA_EMBED_MODEL`, `OLLAMA_LLM_MODEL`, `UPLOAD_DIR`, `CHUNK_SIZE` (int, default 512), `CHUNK_OVERLAP` (int, default 64), `TOP_K` (int, default 5), `SIMILARITY_THRESHOLD` (float, default 0.3), `MAX_TOKENS` (int, default 768), `MAX_TOKENS_FALLBACK` (int, default 1024).

### 4.3 `backend/database.py`

- Use SQLAlchemy async engine with `asyncpg`.
- On startup, run these SQL statements in order:
  1. `CREATE EXTENSION IF NOT EXISTS vector`
  2. Create `documents` table (see models below)
  3. Create `chunks` table (see models below)
- Expose `get_db` dependency for FastAPI routes.
- Expose `recreate_vector_collection()` function — drops and recreates the chunks table plus its index. This is called before any re-ingestion to prevent "collection not found" errors.

### 4.4 `backend/models.py`

Define two SQLAlchemy ORM models:

**`Document`** table — `documents`:
- `id` UUID primary key, default uuid4
- `filename` String, not null
- `original_name` String, not null
- `file_path` String, not null
- `status` String — values: `"pending"`, `"processing"`, `"completed"`, `"failed"`
- `error_message` String, nullable
- `chunk_count` Integer, default 0
- `created_at` DateTime, default utcnow
- `updated_at` DateTime, default utcnow, onupdate utcnow

**`Chunk`** table — `chunks`:
- `id` UUID primary key, default uuid4
- `document_id` UUID, ForeignKey to `documents.id`, CASCADE delete
- `content` Text, not null
- `chunk_index` Integer, not null
- `embedding` Vector(768) — pgvector column, dimension 768 to match nomic-embed-text
- `metadata_` JSONB — stores page number, section info
- `created_at` DateTime, default utcnow

Create an HNSW index on `chunks.embedding` using cosine distance after table creation:
```sql
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
ON chunks USING hnsw (embedding vector_cosine_ops);
```

### 4.5 `backend/services/parser.py`

Implement `parse_pdf(file_path: str) -> list[dict]`:

```
Strategy:
1. Try pdfplumber first
   - Extract text page by page
   - If total extracted text length > 100 chars, return results
2. If pdfplumber fails or returns < 100 chars, fall back to pypdf
3. Each result dict: { "page": int, "text": str }
4. Filter out pages with < 20 chars of text
5. Log which parser was used
6. Raise ParseError if both parsers fail
```

### 4.6 `backend/services/chunker.py`

Implement `chunk_pages(pages: list[dict], chunk_size: int, overlap: int) -> list[dict]`:

```
Strategy:
1. Concatenate all page text with page boundary markers
2. Split into chunks of `chunk_size` tokens (use word-based splitting, not character)
3. Apply `overlap` words of overlap between consecutive chunks
4. Each chunk dict: { "content": str, "chunk_index": int, "metadata": { "page": int } }
5. Minimum chunk size: 50 words — discard smaller chunks
```

### 4.7 `backend/services/embedder.py`

Implement `embed_text(text: str) -> list[float]` and `embed_batch(texts: list[str]) -> list[list[float]]`:

```
- POST to {OLLAMA_URL}/api/embeddings
- Body: { "model": OLLAMA_EMBED_MODEL, "prompt": text }
- Use httpx with timeout=60s
- Retry up to 3 times with exponential backoff (use tenacity)
- embed_batch: call embed_text in sequence (Ollama does not support true batch)
- Return list of floats (768 dimensions for nomic-embed-text)
```

### 4.8 `backend/services/retriever.py`

Implement three retrieval strategies:

**`retrieve_similar(query_embedding, top_k, threshold) -> list[Chunk]`**
Standard cosine similarity search using pgvector `<=>` operator. Filter by `1 - distance >= threshold`.

**`retrieve_threshold(query_embedding, threshold) -> list[Chunk]`**
Return all chunks above the similarity threshold, no top_k cap.

**`retrieve_mmr(query_embedding, top_k, lambda_param=0.5) -> list[Chunk]`**
Maximal Marginal Relevance — reduces redundancy. Fetch top 20 candidates, then iteratively select chunks that balance relevance and diversity using `lambda_param`.

Default strategy used by `/ask` is `retrieve_similar`.

### 4.9 `backend/services/generator.py`

This is the most critical service. Implement `generate_answer(question: str, chunks: list[Chunk]) -> dict`:

```
Pipeline:

STEP 1 — Build context string from chunks
  - Format: "SOURCE [doc_name, page N]:\n{chunk.content}\n\n"
  - Cap total context at 3000 words

STEP 2 — Build prompt
  Use this exact prompt template:

  SYSTEM:
  You are a DEO record assistant. Answer questions using ONLY the
  provided source documents. Do not use outside knowledge.
  If the documents do not contain enough information to answer, say:
  "The provided documents do not contain sufficient information to answer this question."
  Do not include labels like STRUCTURED, FACT, SHORT, or any internal formatting
  markers in your response. Respond in clear plain paragraphs.

  USER:
  Documents:
  {context}

  Question: {question}

STEP 3 — First-pass generation
  POST to {OLLAMA_URL}/api/generate
  Body: { "model": OLLAMA_LLM_MODEL, "prompt": full_prompt, "stream": false,
          "options": { "num_predict": MAX_TOKENS, "temperature": 0.1 } }
  Timeout: 120s

STEP 4 — Check for false refusal
  If response contains "do not contain" or "no information" or "cannot answer":
    AND chunks list is non-empty:
      → Trigger fallback path (Step 5)
  Else:
    → Go to Step 6

STEP 5 — Fallback path (second-pass with larger budget)
  Rebuild prompt with instruction: "The documents DO contain relevant information.
  Extract and summarise the most relevant passages to answer the question."
  Re-call Ollama with MAX_TOKENS_FALLBACK
  If still refuses → trigger extractive rescue (Step 5b)

STEP 5b — Extractive rescue
  Return the top 2 chunk contents directly, prefixed with:
  "Based on the source documents, here is the most relevant information:"

STEP 6 — Check for truncation
  If response ends without sentence-ending punctuation (.!?):
    Re-call Ollama with continuation prompt: "Continue from: {last_50_chars}"
    Append continuation to response
    Mark used_incomplete_detection = True

STEP 7 — Return result dict:
  {
    "answer": str,
    "sources": [{ "document": str, "page": int, "snippet": str (first 150 chars) }],
    "debug": {
      "used_fallback": bool,
      "used_rescue": bool,
      "used_incomplete_detection": bool,
      "answer_length": int,
      "retrieved_count": int,
      "top_similarity_score": float
    }
  }
```

### 4.10 `backend/services/ingestion.py`

Implement `ingest_document(document_id: UUID, db: AsyncSession)` as an async background task:

```
State machine:
1. Set document.status = "processing"
2. Parse PDF → pages
3. Chunk pages → chunks
4. Embed each chunk (call embedder)
5. Insert all chunks into DB in a single bulk insert
6. Set document.status = "completed", document.chunk_count = len(chunks)

On any exception:
  Set document.status = "failed", document.error_message = str(exception)

Concurrency guard:
  Use a module-level asyncio.Lock() called INGESTION_LOCK
  Acquire lock before starting ingestion
  This prevents concurrent ingestion jobs
  Expose is_ingesting() -> bool for the clear-data endpoint to check
```

### 4.11 `backend/routers/documents.py`

Implement these endpoints:

**`POST /api/documents/upload`**
- Accept `multipart/form-data` with `file` field
- Validate: only `.pdf` files, max 50 MB
- Save to `UPLOAD_DIR/{uuid}_{original_name}`
- Create `Document` record with status `"pending"`
- Launch `ingest_document` as `BackgroundTasks` task
- Return: `{ "document_id": str, "status": "pending" }`

**`GET /api/documents`**
- Return list of all documents with id, original_name, status, chunk_count, created_at

**`GET /api/documents/{document_id}/status`**
- Return single document status — used for polling during ingestion

**`DELETE /api/documents/{document_id}`**
- Delete document record (chunks cascade delete via FK)
- Delete the physical file from UPLOAD_DIR
- Return 204

**`POST /api/documents/clear`**
- If `is_ingesting()` returns True → return HTTP 409 with message "Ingestion in progress, cannot clear"
- Call `recreate_vector_collection()` to safely reset vector store
- Delete all Document records
- Delete all files in UPLOAD_DIR
- Return: `{ "message": "All data cleared" }`

### 4.12 `backend/routers/ask.py`

**`POST /api/ask`**
Request body:
```json
{ "question": "string", "retrieval_strategy": "similar|threshold|mmr" }
```

Pipeline:
1. Embed the question
2. Retrieve chunks using selected strategy (default: `"similar"`)
3. If retrieved_count == 0 → return `{ "answer": "No relevant documents found. Please upload DEO PDFs first.", "sources": [], "debug": {...} }`
4. Generate answer
5. Return full result dict from generator

### 4.13 `backend/routers/debug.py`

**`POST /api/debug/retrieve`**
- Takes `{ "question": str, "top_k": int, "threshold": float }`
- Returns raw chunk contents, similarity scores, and metadata without generating an answer
- For diagnosing retrieval quality issues

**`GET /api/debug/stats`**
- Returns: total documents, total chunks, avg chunk length, index size

### 4.14 `backend/main.py`

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db
from routers import documents, ask, debug

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="DEO RAG", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(documents.router)
app.include_router(ask.router)
app.include_router(debug.router)

# IMPORTANT: Mount frontend LAST, after all API routes
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
```

### 4.15 `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The React build must exist at backend/frontend/dist before building this image
# Run: cd frontend && npm run build && cp -r dist ../backend/frontend/dist

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

---

## 5. Frontend — Full Specification

### 5.1 Tech and libraries

- React 18 with Vite
- No UI framework — plain CSS with CSS variables
- `axios` for API calls
- No TypeScript required

### 5.2 Application state

Manage these global state values (use React Context or simple prop drilling):

- `documents: list` — list of uploaded documents
- `ingestionStatus: map[documentId → status]` — polled every 3 seconds while any doc is `"processing"`
- `isClearing: bool` — disable clear button and show warning during active ingestion
- `question: string`
- `answer: object | null` — the full response from `/api/ask`
- `isAsking: bool`

### 5.3 Components

**`UploadPanel`**
- Drag-and-drop zone + file picker button
- Only accepts `.pdf` files
- Shows upload progress
- On success, adds document to list and starts polling its status

**`DocumentList`**
- Shows each document: name, status badge (pending/processing/completed/failed), chunk count
- Status badge colors: gray=pending, amber=processing, green=completed, red=failed
- Delete button per document (with confirmation)
- "Clear all data" button — disabled with tooltip "Ingestion in progress" when backend returns 409

**`QuestionPanel`**
- Text input for question
- Retrieval strategy selector: dropdown with options "Standard", "Threshold", "MMR (diverse)"
- Submit button — disabled when `isAsking` or no documents are completed

**`AnswerDisplay`**
- Shows the answer text
- Shows source citations: document name, page number, snippet
- Collapsible debug panel showing: used_fallback, used_rescue, retrieved_count, top_similarity_score

**`StatusBar`**
- Fixed bottom bar showing: total documents, total chunks, system status (connected/disconnected)
- Polls `/api/debug/stats` every 10 seconds

### 5.4 API calls

All API calls go to `/api/...` — no hardcoded host. Since FastAPI serves both frontend and API on port 8000, relative paths work automatically.

### 5.5 `vite.config.js`

```js
export default {
  build: {
    outDir: '../backend/frontend/dist',  // Build directly into backend folder
    emptyOutDir: true,
  }
}
```

---

## 6. Installer Scripts — Full Specification

### 6.1 `install.sh`

```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  MyApp DEO RAG — Installer"
echo "========================================"
echo ""

# Check Ubuntu
if ! grep -qi ubuntu /etc/os-release 2>/dev/null; then
    echo "Warning: This installer is designed for Ubuntu."
    read -p "Continue anyway? (y/N): " confirm
    [[ "$confirm" != "y" ]] && exit 1
fi

# Install Docker if missing
if ! command -v docker &>/dev/null; then
    echo "[1/6] Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    NEED_RELOGIN=true
else
    echo "[1/6] Docker already installed."
fi

# Install Docker Compose plugin if missing
if ! docker compose version &>/dev/null 2>&1; then
    echo "[2/6] Installing Docker Compose..."
    sudo apt-get install -y docker-compose-plugin
else
    echo "[2/6] Docker Compose already installed."
fi

# Load images
echo "[3/6] Loading application images (this may take a few minutes)..."
docker load -i images/app_backend.tar
docker load -i images/postgres_pgvector.tar
docker load -i images/ollama.tar
echo "      Images loaded."

# Start DB and Ollama first
echo "[4/6] Starting database and AI services..."
docker compose up -d db ollama
echo "      Waiting for services to be ready..."
sleep 10

# Restore Ollama models
echo "[5/6] Restoring AI models..."
docker run --rm \
    -v "$(basename $SCRIPT_DIR)_ollama_models:/data" \
    -v "$SCRIPT_DIR/models:/backup" \
    alpine sh -c "tar xzf /backup/ollama_models.tar.gz -C /data"
echo "      Models restored."

# Start everything
echo "[6/6] Starting all services..."
docker compose up -d
sleep 5

# Desktop shortcut
DESKTOP_FILE="$HOME/Desktop/DEORAG.desktop"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Name=DEO RAG
Comment=DEO Records Q&A System
Exec=bash -c 'cd $SCRIPT_DIR && ./start.sh'
Icon=applications-medicine
Terminal=false
Type=Application
Categories=Office;
EOF
chmod +x "$DESKTOP_FILE"

echo ""
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""
echo "  Open your browser and go to:"
echo "  http://localhost:8000"
echo ""

if [[ "$NEED_RELOGIN" == "true" ]]; then
    echo "  NOTE: Docker was just installed. You may need to"
    echo "  log out and log back in, then run ./start.sh"
    echo ""
fi

# Try to open browser
xdg-open http://localhost:8000 2>/dev/null || true
```

### 6.2 `start.sh`

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting DEO RAG..."
docker compose up -d
sleep 3
echo "Started. Opening browser..."
xdg-open http://localhost:8000 2>/dev/null || echo "Open http://localhost:8000 in your browser."
```

### 6.3 `stop.sh`

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping DEO RAG..."
docker compose down
echo "Stopped. Your data is saved."
```

### 6.4 `scripts/build-distribution.sh`

**Run this on the developer's machine** to prepare the pendrive package:

```bash
#!/bin/bash
set -e

echo "=== Building distribution package ==="

# 1. Build React frontend
echo "[1/6] Building React frontend..."
cd frontend
npm install
npm run build
cd ..

# 2. Build backend Docker image (copies frontend/dist in)
echo "[2/6] Building backend Docker image..."
docker build -t myapp_backend:latest ./backend

# 3. Save all Docker images as tars
echo "[3/6] Saving Docker images..."
mkdir -p images
docker save myapp_backend:latest        -o images/app_backend.tar
docker save pgvector/pgvector:pg16      -o images/postgres_pgvector.tar
docker save ollama/ollama:latest        -o images/ollama.tar

# 4. Pull and export Ollama models
echo "[4/6] Pulling Ollama models (needs internet — do once)..."
mkdir -p models
docker compose up -d ollama
sleep 5
docker exec myapp_ollama ollama pull nomic-embed-text
docker exec myapp_ollama ollama pull llama3
docker compose down

# 5. Export model volume
echo "[5/6] Exporting model data..."
docker run --rm \
    -v myapp-installer_ollama_models:/data \
    -v "$(pwd)/models:/backup" \
    alpine tar czf /backup/ollama_models.tar.gz -C /data .

# 6. Set permissions
echo "[6/6] Setting permissions..."
chmod +x install.sh start.sh stop.sh

echo ""
echo "=== Distribution package ready! ==="
echo "Folder size:"
du -sh .
echo ""
echo "Copy the entire 'myapp-installer/' folder to the USB pendrive."
```

---

## 7. Regression Testing

Create `backend/tests/test_regression.py` using `pytest` and `httpx.AsyncClient`.

Run 10 questions against a seeded test document. Each test must assert:
- HTTP 200 response
- `answer` field is non-empty string
- `answer` does not contain the strings: "STRUCTURED", "FACT", "SHORT" (label leakage check)
- `answer` ends with sentence-ending punctuation: `.`, `!`, or `?` (truncation check)
- `debug.retrieved_count` >= 1
- The response does not contain only "no information" phrasing when `retrieved_count` > 0 (false refusal check)

Target: 10/10 passing, 0 label leaks, 0 truncations, 0 false refusals.

---

## 8. Environment Variables Reference

All configurable via `docker-compose.yml` → `environment` block. No `.env` file needed.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://myapp:myapp@db:5432/myapp` | Postgres connection string |
| `OLLAMA_URL` | `http://ollama:11434` | Ollama service URL |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `OLLAMA_LLM_MODEL` | `llama3` | LLM model name |
| `UPLOAD_DIR` | `/app/uploads` | Where PDFs are stored |
| `CHUNK_SIZE` | `512` | Words per chunk |
| `CHUNK_OVERLAP` | `64` | Overlap between chunks in words |
| `TOP_K` | `5` | Chunks retrieved per query |
| `SIMILARITY_THRESHOLD` | `0.3` | Minimum cosine similarity score |
| `MAX_TOKENS` | `768` | LLM token budget (first pass) |
| `MAX_TOKENS_FALLBACK` | `1024` | LLM token budget (fallback pass) |

---

## 9. Known Failure Modes and Required Guards

The agent must implement all of these. They are not optional:

| Failure | Guard |
|---|---|
| Re-ingestion after clear fails with "collection not found" | Call `recreate_vector_collection()` before writing any new chunks |
| Clear during active ingestion corrupts data | `is_ingesting()` check → HTTP 409 → frontend disables clear button |
| False refusal despite sources existing | Second-pass fallback + extractive rescue path in generator |
| Prompt labels leaking into output | Simplified prompt + explicit ban on label strings |
| Truncated answers for long questions | Incomplete-answer detection + auto-continuation call |
| Both parsers fail on malformed PDF | Raise `ParseError`, set document status to "failed", surface error in UI |

---

## 10. What the Agent Must NOT Do

- Do not use `langchain`, `llamaindex`, or any RAG framework. Implement RAG from scratch as specified.
- Do not hardcode any hostnames, ports, or credentials outside `config.py` and `docker-compose.yml`.
- Do not mount the source code as a Docker volume in production compose — use built images only.
- Do not create a separate Nginx container — FastAPI serves the frontend directly.
- Do not use `WidthType.PERCENTAGE` in any table — not applicable here but noted for completeness.
- Do not skip the `recreate_vector_collection()` call before re-ingestion.
- Do not run more than one uvicorn worker — Ollama model loading is not thread-safe with multiple workers.

---

## 11. Build and Run Order (for the Agent to Follow)

```
1. Scaffold all folders and empty files
2. Write docker-compose.yml
3. Write backend/config.py
4. Write backend/database.py
5. Write backend/models.py
6. Write all backend/services/ files (parser → chunker → embedder → retriever → generator → ingestion)
7. Write all backend/routers/ files
8. Write backend/main.py
9. Write backend/Dockerfile
10. Write all frontend/src/ files
11. Write frontend/vite.config.js and package.json
12. Write install.sh, start.sh, stop.sh
13. Write scripts/build-distribution.sh
14. Write backend/tests/test_regression.py
15. Run: cd frontend && npm install && npm run build
16. Run: docker compose build
17. Run: docker compose up -d
18. Run: pytest backend/tests/test_regression.py
19. Fix any failures until all 10 regression tests pass
20. Run: scripts/build-distribution.sh (to produce the pendrive package)
```

---

## 12. Success Criteria

The application is complete when:

- [ ] `install.sh` runs on a fresh Ubuntu machine and the app is accessible at `http://localhost:8000`
- [ ] A user can upload a DEO PDF and see status change from pending → processing → completed
- [ ] A user can ask a question and receive a grounded answer with source citations
- [ ] Clearing data while ingestion is active returns a clear error message
- [ ] Re-ingesting after a clear works without errors
- [ ] The regression test suite passes 10/10 with 0 label leaks, 0 truncations, 0 false refusals
- [ ] `scripts/build-distribution.sh` produces a folder that can be copied to a pendrive and installed offline
- [ ] All user data (postgres_data, ollama_models, uploads) persists across `stop.sh` / `start.sh` cycles
