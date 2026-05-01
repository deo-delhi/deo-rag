# DEO RAG Adaptation Plan

## Summary

Current architecture: a local RAG app with React/Vite frontend, FastAPI backend, LangChain RetrievalQA, PostgreSQL + pgvector, Ollama/OpenAI-compatible LLMs, and Ollama/HuggingFace/OpenAI embeddings. Ingestion stores uploaded PDFs under `documents/<knowledge_base>/`, parses with Docling first and PyPDF fallback, chunks with `RecursiveCharacterTextSplitter`, writes vectors to per-folder pgvector collections, then `/ask` retrieves chunks, generates a grounded answer, and returns source names/pages plus debug flags.

Adaptation goal: keep the same architecture and tech stack, but rebrand and retarget the system from DEO RAG to Defence Estates Organisation RAG, add Data Library/global retrieval behavior, generate searchable PDFs for scanned files, and upgrade the answer UI to show “Sources Referred” with direct PDF links.

## Key Changes

- Rename domain-facing language from DEO RAG to DEO RAG / Defence Estates Organisation RAG across prompts, API title, frontend labels, docs, env defaults, regression text, and examples.
- Rename the project folder from `medical-rag` to `deo-rag` and update runtime names/defaults to DEO, including `LANGCHAIN_PROJECT=deo-rag`, `COLLECTION_NAME=deo_docs`, and database/container names (`deo_pgvector`, `deo_rag_backend`, `deorag` Postgres database).
- Replace DEO-neutral metadata defaults with DEO-neutral metadata: `document_type="deo_record"`, remove legacy case/person-specific defaults, and add source metadata such as `library`, `source_path`, `source_url`, `searchable_pdf`, and OCR status.
- Reword prompts so the assistant is a DEO records assistant that answers only from uploaded Defence Estates documents and does not provide unsupported legal/administrative conclusions.

## Implementation Changes

- Treat existing knowledge bases as “Data Libraries” in the UI while preserving backend compatibility with the current `knowledge_base` request field.
- Rename the default library to `unflagged`; on startup, migrate `documents/default` to `documents/unflagged` when possible, and keep `default` as a backward-compatible alias.
- Add query scope to `/ask`: `active` searches only the selected Data Library, while `global` searches all Data Libraries, merges top retrieved chunks, and answers from the combined context.
- Add secure source-serving endpoint, for example `GET /sources/{library}/{filename}`, using path validation and `FileResponse` so source links open PDFs in a new tab.
- Extend `/ask` sources to include parent source, page, library, snippet, score, and `source_url`; group duplicate chunks by parent file for the frontend “Sources Referred” panel.
- During ingestion, detect scanned/low-text PDFs and create sidecar searchable PDFs using the existing Python stack: PyMuPDF for PDF/page handling and PaddleOCR/Docling-derived OCR text for invisible text overlays.
- Store searchable PDFs under each library, for example `documents/<library>/.searchable/<filename>`, and return those links in sources when available; fall back to the original PDF for born-digital or OCR-failed files.
- Keep upload support PDF-only for this pass, but make source metadata generic enough for future DOC/TXT support.
- Update the React app branding, localStorage theme key, nav labels, placeholders, overview cards, library controls, and chat panel; add an Active Library / Global scope selector in chat.
- Rename the current “Sources” block to “Sources Referred” and show each parent document as a link with page number and chunk snippet.
- Update all project markdown guides to explain DEO RAG, Data Libraries, Unflagged Library, global search, searchable PDF generation, and source-link behavior.

## Test Plan

- Run backend syntax checks: `py -m py_compile backend/app.py backend/config.py backend/parser.py backend/ingest.py backend/rag_pipeline.py backend/test_regression.py`.
- Run frontend build: `npm --prefix frontend run build`.
- Start the stack and verify `/health`, `/settings`, `/knowledge-bases`, `/documents`, `/ingest/status`, and `/ask`.
- Upload a normal PDF into `unflagged`, ingest it, ask in active-library mode, and confirm answer sources include `source_url`.
- Upload a scanned PDF, ingest it, confirm a searchable sidecar PDF is created, opens from “Sources Referred”, and supports text search in the PDF viewer.
- Create at least two Data Libraries, ingest separate files, ask once in active mode and once in global mode, and confirm global answers can cite sources from multiple libraries.
- Try a path traversal source URL manually and confirm it is rejected.
- After implementation and docs updates, run `py -m graphify update deo-rag`.

## Assumptions

- English-first DEO documents are the target for this pass.
- OCR will use the existing Python dependency direction rather than adding OCRmyPDF/Tesseract.
- “Unflagged Library” is the default catch-all Data Library.
- Existing DEO sample PDFs/test cases are development data and can be reworded or replaced with DEO-oriented examples.
