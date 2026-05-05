# Repository Guidelines

## Project Structure & Module Organization

The project is a Retrieval-Augmented Generation (RAG) system for DEO records. The core application is located in the `deo-rag/` directory.

- **`deo-rag/backend/`**: FastAPI backend handling API, ingestion, and RAG pipeline.
- **`deo-rag/frontend/`**: React (Vite) frontend for user interaction.
- **`deo-rag/documents/`**: Local storage for uploaded PDF documents.
- **`deo-rag/vectorstore/`**: Persistent storage for PostgreSQL/pgvector data.
- **`deo-rag/scripts/`**: Utility scripts for environment setup and maintenance.

The system uses a four-layer architecture:
1. Data Library storage in `documents/`
2. Ingestion and parsing in the FastAPI backend
3. Vector storage in PostgreSQL with pgvector
4. React frontend for management and Q&A

## Build, Test, and Development Commands

### Stack Management
- **Start Stack**: `bash script.sh` (use `--detach` for background execution)
- **Stop Stack**: `bash stop.sh`
- **One-click Setup**: `bash setup-deo-rag.sh`

### Backend Development
Located in `deo-rag/backend/`:
- **Run Dev Server**: `uvicorn app:app --host 0.0.0.0 --port 5200 --reload`
- **Install Dependencies**: `pip install -r requirements.txt`
- **Run Regression Tests**: `python test_regression.py`

### Frontend Development
Located in `deo-rag/frontend/`:
- **Run Dev Server**: `npm run dev`
- **Build Frontend**: `npm run build`
- **Preview Build**: `npm run preview`
- **Install Dependencies**: `npm install`

### Docker
- **Run Services**: `docker compose up` (from `deo-rag/`)

## Coding Style & Naming Conventions

- **Python**: Follows standard FastAPI patterns. Uses `pydantic-settings` for configuration via environment variables.
- **React**: Uses Vite and React 18. Follows standard component-based architecture.
- **Naming**: Descriptive naming for services and endpoints (e.g., `ingest.py`, `rag_pipeline.py`).

## Testing Guidelines

- **Regression Tests**: A regression test suite is available in `deo-rag/backend/test_regression.py`.
- **Test Data**: `test_cases.json` is used for defining test scenarios, and results are stored in `test_results.json`.

## Agent Instructions

When working on this repository, all agents must adhere to these strict rules:

- **Tech Stack Compliance**: Never suggest or use alternative LLM providers or vector databases. The system is hard-coded for **Ollama** and **pgvector**.
- **Parsing Strategy**: Always attempt `pdfplumber` first, then fall back to `pypdf`. For scanned documents, use the `parser.py` logic which handles searchable sidecar generation.
- **State Management**: Ingestion is a stateful background process. Never implement endpoints that could cause race conditions with the `INGESTION_LOCK`.
- **Environment Config**: Always use `config.py` (Pydantic Settings) for configuration. Do not hardcode defaults outside of this file.
- **Pathing**: Ensure all file operations respect the `DOCUMENTS_DIR` and handle Data Library subdirectories (defaulting to `unflagged`).
- **Documentation**: If any major changes are made to the backend architecture, ingestion pipeline, or hardware integration, update [./backend.md](./backend.md) to reflect the new state. This includes changes to OCR layers, chunking strategies, or model providers.

## Prompt Starter for New Agents

If you are starting a new session with an AI agent, provide this prompt:

> "I am working on the DEO RAG project. Please read [./AGENTS.md](./AGENTS.md) and [./deo-rag/ARCHITECTURE_AND_RUNBOOK.md](./deo-rag/ARCHITECTURE_AND_RUNBOOK.md) to understand the architecture, tech stack, and coding conventions before making any changes. Focus on the `deo-rag/` directory for core implementation."
