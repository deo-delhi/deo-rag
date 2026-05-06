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

### 1. Vector Storage & Retrieval
- **Provider**: PostgreSQL with `pgvector`.
- **Hybrid Retrieval**: Combines **BM25** (keyword matching) and **Dense Vectors** (semantic matching) using Reciprocal Rank Fusion (RRF). This ensures precise matching for case names/citations and broad conceptual coverage.
- **Robust Deduplication**: Uses **full content hashing** (MD5) to distinguish between chunks in documents with highly similar structural headers.
- **Metadata Filtering**: Dynamically applies filters *before* slicing the retrieval pool to ensure 100% recall for targeted document queries.

### 2. Context & Expansion
- **Multi-Vector Expansion**: If a summary or keyword-based chunk matches, the system automatically expands it to the full parent text to provide maximum context to the LLM.
- **Large Context Utilization**: Configured to feed up to **100 snippets** (leveraging the 16k context window) to support comprehensive long-form summarization.

### 3. Embedding & Inference
- **Embeddings**: 
  - *Default*: `mxbai-embed-large` via Ollama.
  - *Fallback*: `BAAI/bge-small-en` (HF).
- **LLM**: `qwen2.5:3b-instruct-q5_k_m` via Ollama (Highly reliable for legal summarization).
- **Reranker**: `ms-marco-MiniLM-L-6-v2` for final precision rescoring.

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
