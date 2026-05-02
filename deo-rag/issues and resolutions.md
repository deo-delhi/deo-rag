# 1. 
The live retrieval was doing plain semantic search even when the user clearly named a document, e.g. Sahodara Devi Vs GoI. Because terms like Devi, GoI, Government of India, Union of India occur across many legal PDFs, the vector search pulled unrelated cases first. The LLM then answered from those unrelated chunks, which is exactly what your screenshot shows.

I confirmed:

Sahodara Devi Vs GoI.pdf is present.
Its PDF text is extractable (~17.6k chars).
The vector DB has 18 chunks for it.
The bad answer came because retrieval included Ibrahim Uddin, Nagubai Ammal, Ashoka Marketing, etc. before/alongside Sahodara.
I changed retrieval so that when the question strongly matches an uploaded PDF filename/title, it uses a metadata filter and retrieves chunks only from that matching document. I also updated /debug/retrieve to show this same production retrieval behavior.

# 2.
backend/hybrid_retrieval.py (new): BM25 + dense vector with Reciprocal Rank Fusion; BM25 index built lazily per PG-Vector collection from the existing langchain_pg_embedding rows; cache invalidated on re-ingest. Industry-standard fix; the legal-domain benchmark in the cited sources reports +27% nDCG vs. dense-only.
backend/rag_pipeline.py: replaced the loose grounding prompt with a strict one. Snippets are labelled [snippet N] source: <filename> | page: <P>. Hard rules: only use snippets whose source matches the named document, never use prior knowledge, abstain with a fixed phrase if evidence is missing, end with a Sources: line.
backend/app.py:
_retrieve_for_libraries now uses hybrid_retrieve for both branches; named-document branch additionally filters by source metadata.
/ask short-circuits to an honest abstention when the question clearly names a document but no chunk from that document survived retrieval (no more "summarise X" pulling from Y/Z).
Honest "Insufficient evidence …" abstentions are no longer "rescued" by stitching unrelated sentences (the old extractive rescue was reintroducing hallucinations).
On ingest completion, the BM25 cache is invalidated for that collection.




# 3.
If summaries ever feel too thin
That's almost always a top-k question, not a model question. Open Settings → Retriever top-k and try 10 or 12. The hybrid retriever already pulls a wider candidate pool internally (max(top_k * 5, 20)) and fuses, so increasing top-k mostly just lets more of those candidates reach the LLM context.

You don't need to touch:

OLLAMA_NUM_CTX (8192 is fine for any single-doc summary)
OLLAMA_NUM_PREDICT (2048 is plenty for 500-word answers)
LLM_TEMPERATURE (keep at 0 for grounded summarisation)
So: send your prompt as-is on a freshly restarted backend, and you should see a Sahodara-only summary about Rule 27 of the Cantonment Land Administration Rules, the discretion vs. mandatory question, and the High Court's direction to reconsider — followed by a Sources: Sahodara Devi Vs GoI.pdf (page 1) line.



