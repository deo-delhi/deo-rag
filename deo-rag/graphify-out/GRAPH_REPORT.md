# Graph Report - deo-rag  (2026-05-03)

## Corpus Check
- 15 files · ~26,192 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 203 nodes · 319 edges · 40 communities detected
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 26 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]

## God Nodes (most connected - your core abstractions)
1. `_knowledge_base_dir()` - 15 edges
2. `_knowledge_base_collection_name()` - 13 edges
3. `ask()` - 13 edges
4. `_resolve_knowledge_base_name()` - 12 edges
5. `RegressionTester` - 11 edges
6. `calibrate()` - 10 edges
7. `get_vectorstore()` - 10 edges
8. `_get_ingest_state()` - 8 edges
9. `_retrieve_for_libraries()` - 8 edges
10. `_validate_knowledge_base_name()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `_initialize_hardware_placement()` --calls--> `initialize_hardware_profile()`  [INFERRED]
  backend\app.py → backend\hardware_calibration.py
- `delete_knowledge_base()` --calls--> `get_vectorstore()`  [INFERRED]
  backend\app.py → backend\rag_pipeline.py
- `clear_data()` --calls--> `get_vectorstore()`  [INFERRED]
  backend\app.py → backend\rag_pipeline.py
- `_run_ingest_job()` --calls--> `ingest_to_dict()`  [INFERRED]
  backend\app.py → backend\ingest.py
- `_run_ingest_job()` --calls--> `invalidate_collection()`  [INFERRED]
  backend\app.py → backend\hybrid_retrieval.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.13
Nodes (34): clear_data(), ClearDataRequest, create_knowledge_base(), debug_retrieve_mmr_endpoint(), debug_retrieve_threshold_endpoint(), delete_knowledge_base(), _empty_ingest_state(), _get_ingest_state() (+26 more)

### Community 1 - "Community 1"
Cohesion: 0.13
Nodes (14): load_test_cases(), main(), Regression testing framework for DEO RAG system.  This module tests the RAG, Run a single test case.                  Args:             question: The questio, Run a suite of test cases.                  Args:             test_cases: List o, Generate a summary report of all test results., Test runner for RAG system regression testing., Save test results to a JSON report file. (+6 more)

### Community 2 - "Community 2"
Cohesion: 0.14
Nodes (20): ask(), _extractive_rescue_answer(), _is_abstain_answer(), _looks_incomplete_answer(), _map_llm_error(), Detect if an answer appears to be incomplete or truncated.          Checks for, Convert common provider failures (especially Ollama) into a clear HTTP error, Build a best-effort answer from retrieved chunks when LLM is overly strict. (+12 more)

### Community 3 - "Community 3"
Cohesion: 0.18
Nodes (19): hardware_recalibrate(), hardware_snapshot(), calibrate(), calibrate_and_save(), _classify_adapters(), get_active_profile(), initialize_hardware_profile(), _nvidia_smi_gpu_name() (+11 more)

### Community 4 - "Community 4"
Cohesion: 0.19
Nodes (15): directml_usable(), docling_accelerator_device(), _fallback_torch_accelerator(), get_active_hardware_profile(), paddleocr_use_gpu_preferred(), preferred_torch_device(), pytorch_cuda_can_execute(), pytorch_xpu_can_execute() (+7 more)

### Community 5 - "Community 5"
Cohesion: 0.22
Nodes (13): ingest(), ingest_to_dict(), IngestResult, _load_documents(), _sanitize_documents(), _sanitize_value(), ensure_searchable_pdf(), parse_pdf() (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.2
Nodes (9): Settings, _chunk_count(), _engine(), _get_bm25(), invalidate_collection(), _load_chunks(), Hybrid retrieval (BM25 + dense vector) with Reciprocal Rank Fusion.  BM25 catc, Drop cached BM25 for one collection (call after re-ingest). (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.2
Nodes (12): debug_retrieve_endpoint(), _enrich_doc_metadata(), _group_source_entries(), _matching_sources_for_question(), Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this, _retrieve_for_libraries(), _snippet(), _source_url() (+4 more)

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): True when PyTorch can run CUDA kernels on GPU 0 (not just detect the driver).

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): Device string for HuggingFace embeddings (`cuda`, `xpu`, or `cpu`).

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): Docling `AcceleratorOptions.device` value.

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Detect if an answer appears to be incomplete or truncated.          Checks for:

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): Build a best-effort answer from retrieved chunks when LLM is overly strict.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Create a best-effort searchable sidecar PDF for scanned/low-text PDFs.

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Generate a direct answer from already-retrieved docs when QA chain is overly str

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Debug retrieval to inspect which chunks are being retrieved for a query.     Ret

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Retrieve documents only if they meet a minimum similarity threshold.     Useful

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Use Maximal Marginal Relevance (MMR) to retrieve diverse, relevant documents.

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Detect if an answer appears to be incomplete or truncated.          Checks for:

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Build a best-effort answer from retrieved chunks when LLM is overly strict.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Detect if an answer appears to be incomplete or truncated.          Checks for:

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Build a best-effort answer from retrieved chunks when LLM is overly strict.

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Detect if an answer appears to be incomplete or truncated.          Checks for:

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Build a best-effort answer from retrieved chunks when LLM is overly strict.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Generate a direct answer from already-retrieved docs when QA chain is overly str

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Debug retrieval to inspect which chunks are being retrieved for a query.     Ret

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Retrieve documents only if they meet a minimum similarity threshold.     Useful

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Use Maximal Marginal Relevance (MMR) to retrieve diverse, relevant documents.

## Knowledge Gaps
- **68 isolated node(s):** `Convert common provider failures (especially Ollama) into a clear HTTP error`, `Detect if an answer appears to be incomplete or truncated.          Checks for`, `Build a best-effort answer from retrieved chunks when LLM is overly strict.`, `Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this`, `Debug endpoint: Returns only chunks above a similarity threshold.     Helps ide` (+63 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 14`** (1 nodes): `True when PyTorch can run CUDA kernels on GPU 0 (not just detect the driver).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `Device string for HuggingFace embeddings (`cuda`, `xpu`, or `cpu`).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `Docling `AcceleratorOptions.device` value.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `Detect if an answer appears to be incomplete or truncated.          Checks for:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `Build a best-effort answer from retrieved chunks when LLM is overly strict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Create a best-effort searchable sidecar PDF for scanned/low-text PDFs.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Generate a direct answer from already-retrieved docs when QA chain is overly str`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Debug retrieval to inspect which chunks are being retrieved for a query.     Ret`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Retrieve documents only if they meet a minimum similarity threshold.     Useful`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Use Maximal Marginal Relevance (MMR) to retrieve diverse, relevant documents.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Detect if an answer appears to be incomplete or truncated.          Checks for:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Build a best-effort answer from retrieved chunks when LLM is overly strict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Detect if an answer appears to be incomplete or truncated.          Checks for:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Build a best-effort answer from retrieved chunks when LLM is overly strict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Detect if an answer appears to be incomplete or truncated.          Checks for:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Build a best-effort answer from retrieved chunks when LLM is overly strict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Generate a direct answer from already-retrieved docs when QA chain is overly str`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Debug retrieval to inspect which chunks are being retrieved for a query.     Ret`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Retrieve documents only if they meet a minimum similarity threshold.     Useful`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Use Maximal Marginal Relevance (MMR) to retrieve diverse, relevant documents.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `hardware_snapshot()` connect `Community 3` to `Community 0`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `pytorch_cuda_can_execute()` connect `Community 4` to `Community 3`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `calibrate()` connect `Community 3` to `Community 4`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `ask()` (e.g. with `generate_fallback_answer_from_docs()` and `build_qa_chain()`) actually correct?**
  _`ask()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Convert common provider failures (especially Ollama) into a clear HTTP error`, `Detect if an answer appears to be incomplete or truncated.          Checks for`, `Build a best-effort answer from retrieved chunks when LLM is overly strict.` to the rest of the system?**
  _68 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._