# DEO RAG Project Summary

This is a beginner-friendly project summary created from Graphify's project graph. It explains what the project does, how the main pieces fit together, and where a new developer should start.

## What This Project Is

This project is a DEO RAG application.

RAG means Retrieval-Augmented Generation. In simple terms, the app lets you upload DEO records, turns those documents into searchable knowledge, and then answers questions by looking up the most relevant document chunks before generating a response.

Instead of asking an AI model to answer from memory, the project tries to answer from the user's uploaded DEO material. That is the main idea of the system.

## What A User Can Do

A typical user flow looks like this:

1. Create or choose a Data Library.
2. Upload DEO records, especially PDFs.
3. Start ingestion so the backend can read, clean, parse, and embed the documents.
4. Ask a DEO records question.
5. The system searches the vectorstore for relevant document chunks.
6. The system builds an answer from those retrieved chunks.
7. If the answer looks incomplete, the backend has fallback and rescue logic to produce a better answer from the retrieved material.

The project also includes debug endpoints so a developer can inspect what chunks were retrieved and why an answer may or may not be good.

## Main Parts Of The Project

### Frontend

The frontend starts from `frontend\src\main.jsx`. Graphify only shows a small frontend surface, so the main complexity of the project appears to be in the backend.

For a beginner, think of the frontend as the user interface that talks to the backend. It is where users would upload documents, choose Data Libraries, ask questions, and view answers.

### Backend API

The backend API is centered around `backend\app.py`.

This is the coordination layer. It connects the user-facing actions to the internal RAG logic. Based on the graph, it handles things like:

- Creating a Data Library
- Selecting the active Data Library
- Deleting a Data Library
- Uploading documents
- Starting ingestion
- Checking ingestion status
- Listing documents
- Clearing data
- Asking questions
- Updating settings
- Running retrieval debug endpoints

If you are new to the project, `backend\app.py` is the best place to understand what actions the app exposes.

### Ingestion Pipeline

Document ingestion is handled through `backend\ingest.py`.

Ingestion means turning uploaded documents into data the RAG system can search. Graphify shows the main ingestion function as `ingest()`. It connects to:

- `parse_pdf()` for reading PDF content
- `get_embeddings()` for creating vector representations
- `_sanitize_documents()` for cleaning document data
- `IngestResult` and `ingest_to_dict()` for returning structured results

For a beginner, this part answers the question: "How do uploaded documents become searchable?"

### Retrieval And Answer Generation

Retrieval and answer generation are centered around `backend\rag_pipeline.py`.

The most important function here is `get_vectorstore()`. A vectorstore is where embedded document chunks are stored and searched. When the user asks a question, the system uses the vectorstore to find relevant chunks.

The question-answering endpoint is `ask()` in `backend\app.py`. Graphify shows that `ask()` connects to:

- `_resolve_knowledge_base_name()` to decide which Data Library to use
- `_knowledge_base_collection_name()` to find the correct vector collection
- `get_vectorstore()` to access searchable document chunks
- `build_qa_chain()` to build the question-answering flow
- `generate_fallback_answer_from_docs()` for fallback answers
- `_looks_incomplete_answer()` to detect weak or incomplete answers
- `_extractive_rescue_answer()` to recover an answer from retrieved chunks

For a beginner, this part answers the question: "When I ask something, how does the app find the right information and produce an answer?"

### Data Librarys

The project supports multiple Data Libraries.

A Data Library is like a separate library or collection of documents. For example, one Data Library could contain lease files, while another could contain land records.

Graphify shows several important helpers for this:

- `_knowledge_base_collection_name()`
- `_resolve_knowledge_base_name()`
- `_knowledge_base_dir()`
- `_validate_knowledge_base_name()`
- `_matching_knowledge_base_dirs()`

These helpers are important because the app must keep document files, vectorstore collections, settings, ingestion state, and user requests pointed at the same Data Library.

If these helpers are wrong, the app could search the wrong documents, delete the wrong data, or store vectors in the wrong collection.

### Settings And Runtime State

The app keeps track of settings and ingestion state.

Graphify shows functions such as:

- `get_settings()`
- `update_settings()`
- `_get_ingest_state()`
- `_empty_ingest_state()`
- `get_ingest_status()`
- `list_documents()`

This means the app does not only answer questions. It also tracks what is configured, what documents exist, and whether ingestion is running or completed.

### Debug Tools

The project includes retrieval debugging tools.

These are useful when the answer is bad and you want to know whether the problem is retrieval or generation. Graphify shows these debug paths:

- `debug_retrieve_endpoint()` shows retrieved chunks with similarity scores.
- `debug_retrieve_threshold_endpoint()` returns only chunks above a similarity threshold.
- `debug_retrieve_mmr_endpoint()` uses Maximal Marginal Relevance, which tries to return diverse and relevant chunks.

For a beginner, these tools help answer: "Did the system retrieve the right document chunks before answering?"

### Regression Testing

The project includes a regression testing framework in `backend\test_regression.py`.

Graphify shows the main testing class as `RegressionTester`. It has methods for:

- Loading test cases
- Running one test case
- Running a full test suite
- Checking answer quality
- Checking for leaked internal labels
- Generating a summary
- Saving a JSON report
- Printing a console summary

This is important because RAG systems can change behavior when prompts, retrieval settings, embeddings, or document parsing logic changes. Regression tests help catch when answer quality gets worse.

## How The Pieces Work Together

Here is the project in plain language:

1. The user interacts with the frontend.
2. The frontend calls the backend API.
3. The backend manages Data Libraries and uploaded documents.
4. Uploaded documents go through ingestion.
5. Ingestion parses and cleans documents, then creates embeddings.
6. Embeddings are stored in a vectorstore.
7. When the user asks a question, the backend resolves the active Data Library.
8. The backend searches the correct vectorstore for relevant chunks.
9. The QA pipeline builds an answer from those chunks.
10. Debug tools help inspect retrieval quality.
11. Regression tests help verify that the RAG system still behaves well over time.

## Most Important Concepts For A Beginner

### RAG

RAG means the model answers using retrieved documents, not just its own training memory.

### Data Library

A Data Library is a named collection of uploaded documents and their vector data.

### Ingestion

Ingestion is the process of reading documents, cleaning them, splitting or preparing them, and turning them into embeddings.

### Embeddings

Embeddings are numerical representations of text. They let the app search by meaning instead of exact words.

### Vectorstore

The vectorstore stores embeddings and lets the app find document chunks similar to a user's question.

### QA Chain

The QA chain is the flow that combines the user's question, retrieved document chunks, and the language model to produce an answer.

### Regression Test

A regression test checks that the app still behaves correctly after code changes.

## Key Files To Know

- `backend\app.py`: Main backend API and orchestration layer.
- `backend\rag_pipeline.py`: Retrieval, vectorstore access, embeddings, QA chain, and debug retrieval logic.
- `backend\ingest.py`: Document ingestion pipeline.
- `backend\config.py`: Settings/configuration support.
- `backend\test_regression.py`: RAG regression testing framework.
- `frontend\src\main.jsx`: Frontend entry point.

## What To Study First

If you are new to this project, study it in this order:

1. Start with the user flow: upload documents, ingest them, ask a question.
2. Look at `backend\app.py` to understand the API actions.
3. Follow ingestion through `ingest()`.
4. Follow question answering through `ask()`.
5. Understand `get_vectorstore()` because it connects retrieval, QA, debug tools, and data management.
6. Learn the knowledge-base helpers because they keep each collection of documents separate.
7. Use the debug retrieval endpoints when answers seem wrong.
8. Use `RegressionTester` to understand how answer quality is checked.

## Important Design Notes

The most important design idea in the project is separation by Data Library. Many core functions exist to make sure the app reads from and writes to the correct Data Library.

The second important idea is retrieval quality. The app has normal retrieval, threshold-based retrieval, MMR retrieval, fallback answer generation, and rescue logic for incomplete answers. This suggests the project is designed not only to answer questions, but also to inspect and improve answer quality.

The third important idea is testability. The regression testing framework exists because DEO RAG quality can degrade silently if retrieval, prompts, parsing, or settings change.

## Beginner Mental Model

Think of the app like a DEO-record librarian:

- The user gives the librarian documents.
- The ingestion pipeline reads and indexes those documents.
- The vectorstore becomes the librarian's searchable memory.
- The user asks a question.
- The retrieval system finds the most relevant pages or chunks.
- The QA system writes an answer using those chunks.
- Debug tools show what the librarian actually found.
- Regression tests check whether the librarian is still answering well after changes.

That is the project at a high level.
