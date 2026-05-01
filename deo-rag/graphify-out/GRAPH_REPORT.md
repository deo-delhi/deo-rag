# Graph Report - deo-rag  (2026-05-02)

## Corpus Check
- 12 files · ~20,114 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 135 nodes · 215 edges · 27 communities detected
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 14 edges (avg confidence: 0.8)
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

## God Nodes (most connected - your core abstractions)
1. `_knowledge_base_dir()` - 14 edges
2. `_knowledge_base_collection_name()` - 14 edges
3. `_resolve_knowledge_base_name()` - 12 edges
4. `ask()` - 12 edges
5. `RegressionTester` - 11 edges
6. `get_vectorstore()` - 10 edges
7. `_get_ingest_state()` - 8 edges
8. `_validate_knowledge_base_name()` - 7 edges
9. `ingest()` - 7 edges
10. `clear_data()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `_retrieve_for_libraries()` --calls--> `retrieve_with_scores()`  [INFERRED]
  backend\app.py → backend\rag_pipeline.py
- `delete_knowledge_base()` --calls--> `get_vectorstore()`  [INFERRED]
  backend\app.py → backend\rag_pipeline.py
- `clear_data()` --calls--> `get_vectorstore()`  [INFERRED]
  backend\app.py → backend\rag_pipeline.py
- `_run_ingest_job()` --calls--> `ingest_to_dict()`  [INFERRED]
  backend\app.py → backend\ingest.py
- `debug_retrieve_endpoint()` --calls--> `debug_retrieve()`  [INFERRED]
  backend\app.py → backend\rag_pipeline.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.13
Nodes (14): load_test_cases(), main(), Regression testing framework for DEO RAG system.  This module tests the RAG, Run a single test case.                  Args:             question: The questio, Run a suite of test cases.                  Args:             test_cases: List o, Generate a summary report of all test results., Test runner for RAG system regression testing., Save test results to a JSON report file. (+6 more)

### Community 1 - "Community 1"
Cohesion: 0.15
Nodes (20): ask(), _extractive_rescue_answer(), _looks_incomplete_answer(), _map_llm_error(), Detect if an answer appears to be incomplete or truncated.          Checks for:, Build a best-effort answer from retrieved chunks when LLM is overly strict., Convert common provider failures (especially Ollama) into a clear HTTP error, build_qa_chain() (+12 more)

### Community 2 - "Community 2"
Cohesion: 0.18
Nodes (14): Settings, ingest(), ingest_to_dict(), IngestResult, _load_documents(), _sanitize_documents(), _sanitize_value(), ensure_searchable_pdf() (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.26
Nodes (9): delete_knowledge_base(), _enrich_doc_metadata(), get_settings(), _group_source_entries(), _matching_knowledge_base_dirs(), _retrieve_for_libraries(), _snippet(), _source_url() (+1 more)

### Community 4 - "Community 4"
Cohesion: 0.2
Nodes (10): debug_retrieve_endpoint(), debug_retrieve_mmr_endpoint(), debug_retrieve_threshold_endpoint(), get_source_pdf(), list_documents(), Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M, Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this, Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden (+2 more)

### Community 5 - "Community 5"
Cohesion: 0.43
Nodes (7): create_knowledge_base(), _knowledge_base_dir(), _list_knowledge_bases(), _migrate_legacy_default_library(), _migrate_legacy_root_pdfs(), set_active_knowledge_base(), _validate_knowledge_base_name()

### Community 6 - "Community 6"
Cohesion: 0.43
Nodes (7): clear_data(), _empty_ingest_state(), _get_ingest_state(), get_ingest_status(), _knowledge_base_collection_name(), _run_ingest_job(), start_ingestion()

### Community 7 - "Community 7"
Cohesion: 0.33
Nodes (6): ClearDataRequest, IngestRequest, KnowledgeBaseRequest, Query, SettingsUpdateRequest, BaseModel

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): Detect if an answer appears to be incomplete or truncated.          Checks for:

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): Build a best-effort answer from retrieved chunks when LLM is overly strict.

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Detect if an answer appears to be incomplete or truncated.          Checks for:

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): Build a best-effort answer from retrieved chunks when LLM is overly strict.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Detect if an answer appears to be incomplete or truncated.          Checks for:

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Build a best-effort answer from retrieved chunks when LLM is overly strict.

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Generate a direct answer from already-retrieved docs when QA chain is overly str

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Debug retrieval to inspect which chunks are being retrieved for a query.     Ret

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Retrieve documents only if they meet a minimum similarity threshold.     Useful

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Use Maximal Marginal Relevance (MMR) to retrieve diverse, relevant documents.

## Knowledge Gaps
- **43 isolated node(s):** `Convert common provider failures (especially Ollama) into a clear HTTP error`, `Detect if an answer appears to be incomplete or truncated.          Checks for:`, `Build a best-effort answer from retrieved chunks when LLM is overly strict.`, `Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this`, `Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 14`** (1 nodes): `Detect if an answer appears to be incomplete or truncated.          Checks for:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `Build a best-effort answer from retrieved chunks when LLM is overly strict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Detect if an answer appears to be incomplete or truncated.          Checks for:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Build a best-effort answer from retrieved chunks when LLM is overly strict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Detect if an answer appears to be incomplete or truncated.          Checks for:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Build a best-effort answer from retrieved chunks when LLM is overly strict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Debug endpoint: Shows all retrieved chunks with similarity scores.     Use this`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Debug endpoint: Returns only chunks above a similarity threshold.     Helps iden`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.     M`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Generate a direct answer from already-retrieved docs when QA chain is overly str`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Debug retrieval to inspect which chunks are being retrieved for a query.     Ret`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Retrieve documents only if they meet a minimum similarity threshold.     Useful`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Use Maximal Marginal Relevance (MMR) to retrieve diverse, relevant documents.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ask()` connect `Community 1` to `Community 3`, `Community 4`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Why does `ingest()` connect `Community 2` to `Community 1`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `ask()` (e.g. with `generate_fallback_answer_from_docs()` and `build_qa_chain()`) actually correct?**
  _`ask()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Convert common provider failures (especially Ollama) into a clear HTTP error`, `Detect if an answer appears to be incomplete or truncated.          Checks for:`, `Build a best-effort answer from retrieved chunks when LLM is overly strict.` to the rest of the system?**
  _43 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._