I have completed the optimization and enhancement of the DEO RAG system.

### **Summary of Changes**

1.  **High-Accuracy Ingestion Pipeline**:
    *   **OCRmyPDF Integration**: Replaced custom PaddleOCR logic with `OCRmyPDF` for professional-grade PDF normalization.
    *   **Docling Integration**: Implemented `Docling` for layout-aware Markdown extraction, preserving complex tables and headers.
    *   **Hardware Acceleration**: Configured `Docling` and `OCRmyPDF` to utilize **CUDA** (GPU) and multi-core CPUs for maximum performance.
2.  **Semantic Retrieval Upgrade**:
    *   **BGE-Large Embeddings**: Migrated the embedding model to **`BAAI/bge-large-en-v1.5`** (via HuggingFace) to ensure top-tier accuracy for legal and administrative texts.
    *   **Vector Store Refresh**: Successfully re-ingested all 20 document variants into the PostgreSQL/pgvector database using the new high-capacity embeddings.
3.  **Interactive Admin Dashboard**:
    *   **Dynamic Model Selection**: Added dropdown menus for **LLM Model** and **Reranker** selection directly in the Query interface.
    *   **Live Backend Integration**: Created a new `/available-models` endpoint that fetches real-time tags from the Ollama API.
    *   **Per-Request Overrides**: Updated the RAG pipeline to support dynamic model switching without requiring a server restart.
4.  **Documentation**:
    *   Created [./backend.md](./backend.md) with detailed architecture and ingestion notes.
    *   Updated [./AGENTS.md](./AGENTS.md) with new guidelines for maintaining documentation.

### **Verification Results**
*   **Ingestion**: 20/20 files processed and indexed successfully.
*   **Accuracy**: A demo query on the `Usha Kapoor` case correctly identified **GLR Survey No. 214** with high-confidence citations.
*   **Hardware**: Confirmed CUDA utilization for layout parsing and embedding generation.

The system is now optimized for accuracy, provides flexible controls for benchmarking, and is fully documented for future development.

