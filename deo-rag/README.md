# DEO RAG

This repository contains a local DEO record RAG application with a FastAPI backend, a React frontend, PostgreSQL + pgvector storage, and either Ollama or OpenAI-compatible model providers depending on configuration.

The full operational documentation is here:

- [Architecture and Runbook](ARCHITECTURE_AND_RUNBOOK.md)

If you just want the short version:

- Backend API: `http://127.0.0.1:5200`
- Frontend UI: `http://127.0.0.1:5201`
- PostgreSQL + pgvector: `localhost:5202`

The app supports:

- PDF upload
- PDF parsing with Docling-first and PyPDF fallback
- Searchable sidecar PDFs for scanned/low-text PDFs when OCR is available
- Chunking and embedding into pgvector
- Retrieval-augmented question answering
- Data Libraries, including the default `unflagged` library
- Active-library and global search modes
- Sources Referred links that open the cited parent PDF
- Clear-data and re-ingest flows

For day-to-day operations, use `bash script.sh` to start the stack and `bash stop.sh` to shut it down.
