# Backend Architecture - DEO RAG

This document outlines the backend architecture, document processing pipeline, and ingestion flow for the DEO RAG system.

## Overview

The backend is built with **FastAPI** and orchestrates the Retrieval-Augmented Generation (RAG) pipeline. It handles document ingestion, vector storage, and query processing using a combination of local LLMs and specialized parsing tools.

## Document Processing Pipeline

The ingestion pipeline is designed to handle complex DEO records, including scanned PDFs and legal documents with structured tables.

### 1. Parsing Layers
We use a multi-layered approach to ensure maximum text extraction quality:
- **OCR Layer (OCRmyPDF)**: Scanned documents are first processed via `OCRmyPDF`. This generates a searchable sidecar/layer, normalizes the PDF, and handles deskewing/cleansing.
- **Layout Parsing (Docling)**: After normalization, `Docling` is used for layout-aware parsing. It identifies tables, headers, and structural elements, converting them into structured Markdown.
- **Fallback (pdfplumber/PyPDF)**: For simple digital PDFs or if primary layers fail, we fallback to standard text extractors.

### 2. Chunking Strategy
- **Layout-Aware Chunking**: We use a `RecursiveCharacterTextSplitter` with Markdown-specific separators (`#`, `##`, `###`). This ensures that chunks respect document sections and maintain structural context.
- **Metadata**: Each chunk carries metadata including `source`, `page`, and section headers.

## RAG Pipeline

### 1. Vector Storage
- **Provider**: PostgreSQL with `pgvector` (via ChromaDB or direct pgvector integration).
- **Collection Management**: Documents are grouped by "Data Library" subdirectories (e.g., `unflagged`, `proprietary`).

### 2. Embedding & Inference
- **Embeddings**: 
  - *Default*: `mxbai-embed-large` via Ollama (High accuracy).
  - *Low VRAM Optimized*: `BAAI/bge-small-en-v1.5` via HuggingFace (Saves ~600MB VRAM).
- **LLM**: `llama3.2` via Ollama (Optimized for 3B parameter efficiency).
- **Reranker**: `ms-marco-MiniLM-L-6-v2` (Cross-encoder) for refining top-k results.

## Hardware Acceleration

To minimize latency on consumer hardware (e.g., 4GB VRAM):
- **Docling**: Configured to use **CUDA** for layout detection models.
- **OCRmyPDF**: Optimized for multi-core CPU execution.
- **Ollama**: Runs in a separate process, allowing for flexible memory management/swapping.

## Ingestion Flow

1. **Upload**: Files are saved to `DOCUMENTS_DIR`.
2. **Locking**: An `INGESTION_LOCK` prevents concurrent ingestion tasks.
3. **Pipeline**: `parser.py` -> `ingest.py` -> Vector Store.
4. **State Management**: Ingestion status is tracked to provide feedback to the frontend.
