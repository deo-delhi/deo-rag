# RAG Pipeline: Root-Cause Diagnosis & Fixes

## The Problem

When asked to summarize "UoI vs Dinshaw Anklesaria", the RAG:
- ✅ Found the correct PDF
- ❌ Retrieved only **early historical chunks** (property background)
- ❌ Completely **missed** the Supreme Court judgment, ruling, and outcome
- ❌ **Hallucinated** that "further details are needed" when the full judgment was in the PDF
- ❌ Got dates wrong and misattributed ownership

## Root Causes Identified (7 Issues)

### Issue 1: `RETRIEVER_TOP_K=4` — Far Too Few Chunks
**Impact: CRITICAL**

Only 4 chunks are retrieved. A Supreme Court judgment is 15-40 pages. With 1000-char chunks, only ~2 pages of content reach the LLM. The historical background appears first in the document, so those early chunks get retrieved, while the actual ruling (later in the document) is never seen.

**Fix:** `RETRIEVER_TOP_K=20` → retrieves ~15-20 pages of content covering the full case.

---

### Issue 2: `OLLAMA_NUM_CTX=4096` — Context Window Starvation
**Impact: CRITICAL**

Even if we retrieve more chunks, the LLM can only process 4096 tokens (~3000 words). A 1000-word summary question needs:
- ~800 tokens for the prompt template
- ~1500 tokens for the answer
- That leaves **~1800 tokens for context** — barely 5-6 chunks

The model literally **cannot read** enough source material to produce a good summary.

**Fix:** `OLLAMA_NUM_CTX=16384` — allows feeding 20+ chunks while leaving room for a detailed answer.

---

### Issue 3: `OLLAMA_NUM_PREDICT=512` — Answer Truncation
**Impact: HIGH**

The user asked for a 1000-word summary. 512 tokens ≈ 380 words. The model is **physically unable** to produce the requested output. It truncates mid-thought, leading to incomplete analysis.

**Fix:** `OLLAMA_NUM_PREDICT=2048` — allows 1500+ word responses for comprehensive summaries.

---

### Issue 4: `INGEST_CHUNK_SIZE=1000` / `INGEST_CHUNK_OVERLAP=150` — Chunks Too Small for Legal Documents
**Impact: HIGH**

Legal judgments have long, interconnected paragraphs. A 1000-character chunk (~150 words) often splits a single legal argument across 2-3 chunks. The overlap of 150 chars isn't enough to maintain continuity.

**Fix:** `INGEST_CHUNK_SIZE=1500`, `INGEST_CHUNK_OVERLAP=300` — keeps legal paragraphs intact while maintaining cross-chunk context.

---

### Issue 5: Embedding Model `bge-small-en` — Too Weak for Legal Text
**Impact: MEDIUM-HIGH**

`bge-small-en` (384 dimensions, 33M params) struggles with legal terminology, case names, and complex queries. It can't differentiate between "property dispute background" and "Supreme Court judgment and ruling" — both are semantically related to the case name.

**Fix:** Upgrade to `BAAI/bge-base-en-v1.5` (768 dimensions, 110M params) — significantly better at distinguishing legal concepts. Still runs on T1000 4GB GPU.

---

### Issue 6: No Context Enrichment — Chunks Lose Document-Level Awareness
**Impact: HIGH**

Each chunk is stored as raw text with no document-level context. When the retriever finds a chunk about "the bungalow was bequeathed", there's no indication this is from the "factual background" section vs. the "Supreme Court ruling" section.

**Fix:** Prepend document/source metadata to each chunk before embedding: `"[Source: UoI_vs_Dinshaw.pdf | Page: 15] ..."`. This helps the embedding model and LLM both orient within the document.

---

### Issue 7: `generate_fallback_answer_from_docs` Only Uses 6 Chunks
**Impact: HIGH**

In [rag_pipeline.py:260](file:///home/ashok/Documents/ritik/code/deo-rag/deo-rag/backend/rag_pipeline.py#L260), `docs[:6]` hard-caps the context to 6 chunks regardless of how many were retrieved. For case summaries, we need all retrieved chunks.

**Fix:** Use all available chunks (up to context window capacity) instead of hard-capping at 6.

---

## Configuration Changes Summary

| Parameter | Before | After | Why |
|---|---|---|---|
| `RETRIEVER_TOP_K` | 4 | 20 | Need full case coverage |
| `OLLAMA_NUM_CTX` | 4096 | 16384 | Feed all chunks to LLM |
| `OLLAMA_NUM_PREDICT` | 512 | 2048 | Allow long answers |
| `INGEST_CHUNK_SIZE` | 1000 | 1500 | Keep legal paragraphs whole |
| `INGEST_CHUNK_OVERLAP` | 150 | 300 | Better cross-chunk context |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en` | `BAAI/bge-base-en-v1.5` | Better legal text retrieval |

> [!IMPORTANT]
> After changing chunk size, overlap, or embedding model, you **must re-ingest** all documents.

## Code Changes Summary

1. **Context-enriched chunking** — prepend source/page metadata to each chunk
2. **Dynamic context window** — use all retrieved chunks up to token budget
3. **Better prompt engineering** — structured prompts that prevent hallucination
4. **Improved answer quality detection** — smarter incomplete answer logic
