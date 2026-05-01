# Retrieval Debugging Guide for DEO RAG

## Problem Statement
Your RAG system is returning vague answers. This usually happens when:
1. **Poor chunk retrieval** - The retrieved documents aren't relevant to the query
2. **Embeddings issues** - Your embedding model isn't capturing semantic meaning well
3. **Chunk size/overlap** - Text is split poorly, losing context
4. **Low similarity scores** - Retrieved chunks don't match the query well

---

## Quick Start: Debug Your Retrieval

### 1. **Check What's Being Retrieved** (Basic Debugging)

Use the new debug endpoints in the API:

```bash
# Test what chunks are retrieved with similarity scores
curl -s -X POST http://127.0.0.1:5200/debug/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is estate records?"}'
```

**What to look for:**
- Check the `similarity_score` values
- Are scores above 0.5? (Good) or below 0.3? (Problem)
- Is the content related to your question?
- Are there any duplicate/redundant chunks?

---

### 2. **Try MMR (Maximal Marginal Relevance)** (Better Diversity)

MMR reduces redundant chunks while keeping relevant ones:

```bash
curl -s -X POST http://127.0.0.1:5200/debug/retrieve-mmr \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is estate records?","lambda_mult":0.5}'
```

**lambda_mult settings:**
- `1.0` = Pure relevance (like normal similarity)
- `0.5` = Balance (recommended - good relevance + diversity)
- `0.0` = Pure diversity (removes redundancy)

---

### 3. **Use Similarity Threshold Filtering** (Quality Control)

Only retrieve chunks above a confidence threshold:

```bash
curl -s -X POST http://127.0.0.1:5200/debug/retrieve-threshold \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is estate records?","threshold":0.5}'
```

**Threshold interpretation:**
- `0.3-0.4` = Very permissive, many false positives
- `0.5-0.6` = Good balance (recommended starting point)
- `0.7+` = Very strict, might miss relevant docs

---

## Root Cause Analysis

### Problem: Low Similarity Scores (< 0.3)

**Causes:**
- Query and documents use very different vocabulary
- Embedding model not trained on Defence Estates terminology
- Questions too vague or abstract

**Solutions:**
1. **Try a DEO-specific embedding model:**
   ```env
   EMBEDDING_MODEL=med-mxbai-embed-large:latest
   # or
   EMBEDDING_MODEL=nomic-embed-text
   ```

2. **Adjust chunking strategy** (in environment variables):
   ```env
   INGEST_CHUNK_SIZE=1000    # Larger chunks = more context
   INGEST_CHUNK_OVERLAP=200   # More overlap = better continuity
   ```

3. **Re-ingest with better chunks:**
   ```bash
   # Clear old vectorstore
   curl -s -X POST http://127.0.0.1:5200/data/clear \
     -H 'Content-Type: application/json' \
     -d '{"delete_files":false,"delete_vectorstore":true}'
   
   # Re-ingest with new settings
   curl -s -X POST http://127.0.0.1:5200/ingest/start \
     -H 'Content-Type: application/json' \
     -d '{"chunk_size":1000,"chunk_overlap":200}'
   ```

---

### Problem: Too Many Redundant Chunks

**Solutions:**
1. Use MMR with `lambda_mult=0.3-0.5` to reduce redundancy
2. Increase chunk size to reduce overlapping chunks
3. Decrease chunk overlap

---

### Problem: Vague/Generic Answers Despite Good Chunks

**This means retrieval is good but LLM is not using the context well.**

**Solutions:**
1. **Increase LLM temperature (for creativity):**
   ```bash
   curl -s -X PUT http://127.0.0.1:5200/settings \
     -H 'Content-Type: application/json' \
     -d '{"llm_temperature":0.3}'
   ```

2. **Increase context window size:**
   ```bash
   curl -s -X PUT http://127.0.0.1:5200/settings \
     -H 'Content-Type: application/json' \
     -d '{"ollama_num_ctx":16384}'
   ```

3. **Increase prediction tokens:**
   ```bash
   curl -s -X PUT http://127.0.0.1:5200/settings \
     -H 'Content-Type: application/json' \
     -d '{"ollama_num_predict":1024}'
   ```

4. **Try a better LLM model:**
   ```env
   LLM_MODEL=llama2-uncensored:latest
   # or
   LLM_MODEL=mistral:latest
   ```

---

## Debugging Workflow

### Step 1: Test Basic Retrieval
```bash
curl -s -X POST http://127.0.0.1:5200/debug/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"question":"Your test question"}' | jq '.documents[] | {rank, similarity_score, source, preview: .content_preview}'
```

### Step 2: Check Similarity Scores
- All < 0.3? → Embedding or chunking issue
- 0.3-0.6? → Acceptable but could improve
- > 0.6? → Good retrieval

### Step 3: Try MMR if Too Many Similar Results
```bash
curl -s -X POST http://127.0.0.1:5200/debug/retrieve-mmr \
  -H 'Content-Type: application/json' \
  -d '{"question":"Your test question","lambda_mult":0.5}' | jq '.documents[] | {rank, source, preview: .content_preview}'
```

### Step 4: Check Answer Quality
Test with `/ask` endpoint and see if answers improved:
```bash
curl -s -X POST http://127.0.0.1:5200/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Your test question"}'
```

---

## Configuration Tuning Guide

### For Better Relevance (More Precise Answers)
```env
RETRIEVER_TOP_K=3             # Fewer, better-ranked results
INGEST_CHUNK_SIZE=1000        # Larger chunks with full context
INGEST_CHUNK_OVERLAP=200      # Good continuity between chunks
LLM_TEMPERATURE=0.0           # Deterministic answers using context
```

### For Better Coverage (More Complete Answers)
```env
RETRIEVER_TOP_K=8             # More diverse results
INGEST_CHUNK_SIZE=600         # Smaller chunks for specificity
INGEST_CHUNK_OVERLAP=100      # Less redundancy
LLM_TEMPERATURE=0.2           # Slight creativity to synthesize
```

### For Better Speed (Faster Responses)
```env
RETRIEVER_TOP_K=3             # Fewer chunks to process
INGEST_CHUNK_SIZE=1200        # Fewer chunks in vectorstore
EMBEDDING_MODEL=bge-small-en  # Faster but less accurate
```

---

## Recommended Testing Questions

Test with these to debug:

1. **Fact-based**: "What is the normal blood glucose level?"
   - Should return specific numbers from documents

2. **Descriptive**: "Explain the pathophysiology of type 2 estate records"
   - Should return comprehensive mechanism explanation

3. **Comparative**: "Compare type 1 and type 2 estate records"
   - Should return contrasting information from documents

---

## Monitoring Retrieval Quality

### Key Metrics to Track

1. **Average Similarity Score**
   - Good: 0.5-0.8
   - Poor: < 0.3

2. **Top-K Diversity**
   - Use MMR to measure if top results are similar or diverse

3. **Answer Consistency**
   - Ask the same question multiple times
   - Should get similar answers with low temperature

---

## Python Script for Batch Testing

Add this to test retrieval locally:

```python
from backend.rag_pipeline import debug_retrieve, debug_mmr_retrieve

test_questions = [
    "What is estate records?",
    "How is estate records diagnosed?",
    "What are estate records complications?",
]

for q in test_questions:
    print(f"\n{'='*60}")
    print(f"Question: {q}")
    print('='*60)
    
    results = debug_retrieve(q, include_scores=True)
    
    print(f"\nRetrieved {len(results)} documents:")
    for doc in results:
        print(f"\n  #{doc['rank']} (Score: {doc['similarity_score']})")
        print(f"  Source: {doc['source']}")
        print(f"  Preview: {doc['content_preview'][:200]}...")
```

Run it locally:
```bash
cd /home/ashok/Desktop/RAGSYSTEM/deo-rag
/home/ashok/Desktop/RAGSYSTEM/.venv/bin/python -c "your_script_here"
```

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| All similarity scores < 0.3 | Wrong embedding model or vocabulary mismatch | Try DEO-specific embeddings or re-chunk |
| Duplicate chunks in top-k | Overlapping chunks or poor diversity | Use MMR or increase overlap threshold |
| Answers are too generic | LLM not using context effectively | Reduce temperature, increase context size |
| Slow retrieval | Too many chunks or large context window | Reduce top_k, use smaller chunks |
| Missing relevant info | Not retrieving correct chunks | Increase top_k, lower similarity threshold |

---

## Next Steps

1. ✅ Run `/debug/retrieve` with your test questions
2. ✅ Note the similarity scores
3. ✅ Compare with MMR results (`/debug/retrieve-mmr`)
4. ✅ Identify the root cause from above
5. ✅ Adjust settings and re-test
6. ✅ Monitor improvements with `/ask` endpoint
