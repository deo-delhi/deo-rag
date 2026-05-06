# DEO RAG System - Improvements & Troubleshooting Guide

## What Was Fixed

### 1. **Configuration Improvements** (.env)
- **EMBEDDING_PROVIDER**: Changed from `huggingface` (small model) to `ollama` with `mxbai-embed-large` for better semantic understanding of legal text
- **INGEST_CHUNK_SIZE**: Reduced from 1000 to 800 for better chunk boundaries
- **INGEST_CHUNK_OVERLAP**: Increased from 150 to 250 to preserve context continuity in legal documents
- **RETRIEVER_TOP_K**: Increased to 20 to retrieve more chunks for comprehensive summaries
- **LLM_TEMPERATURE**: Changed from 0 to 0.1 to allow slight synthesis across chunks while staying grounded
- **OLLAMA_NUM_CTX**: Increased to 12288 for longer legal cases
- **OLLAMA_NUM_PREDICT**: Increased to 3072 for comprehensive summaries

### 2. **Prompt Engineering Improvements**

#### Main Prompt (PROMPT)
- Added **Comprehensive Coverage Requirements**: Now explicitly tells LLM to include background, timeline, parties, issues, rulings, and outcomes
- Added **Faithful to Source** constraints: Preserves exact dates/years, preserves all parties
- Added **Structure Guidelines**: Uses clear sections for summaries
- Prevents hallucinations about missing information

#### Fallback Prompt (FALLBACK_ANSWER_PROMPT)
- Added **Mandatory Structure for Case Summaries**: Background, Parties, Timeline, Legal Issues, Court Proceedings, Judgment, Outcome
- Added **Synthesis Rules**: Tells LLM to synthesize across snippets WITH references
- Prevents "more information needed" cop-outs when information exists
- Focuses on completeness over brevity

### 3. **Chunking Strategy Improvements**

New `_create_legal_document_splitter()` function uses optimized separator hierarchy:
1. Triple newlines (section breaks)
2. Double newlines (paragraph breaks - most common in legal docs)
3. Single newlines
4. Sentence boundaries (`. `, `! `, `? `)
5. Space characters as fallback

Benefits:
- Keeps legal sections together
- Preserves paragraph context
- Reduces orphaned sentences

### 4. **Query Expansion** 

New `_expand_legal_query()` function handles case name variations:
- "vs" ↔ "versus"
- "UoI" ↔ "Union of India"
- "GoI" ↔ "Government of India"

This ensures cases with differently-formatted names are still found.

---

## How to Use the Improved System

### Step 1: Re-ingest Your Documents

With new chunking strategy and embedding model:

```bash
# Clear old data
curl -X POST http://localhost:5200/data/clear \
  -H 'Content-Type: application/json' \
  -d '{"delete_files":false,"delete_vectorstore":true}'

# Re-ingest with improved settings
curl -X POST http://localhost:5200/ingest/start \
  -H 'Content-Type: application/json' \
  -d '{"chunk_size":800,"chunk_overlap":250,"replace_collection":false}'

# Monitor progress
curl http://localhost:5200/ingest/status
```

### Step 2: Test Retrieval Quality

Debug what chunks are being retrieved:

```bash
curl -X POST http://localhost:5200/debug/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"question":"summarise the UoI vs Dinshaw Anklaesari case"}'
```

Look for:
- ✅ Scores above 0.5 (good)
- ✅ Varied content (not just repeated phrases)
- ✅ Chunks from the correct PDF
- ✅ Key case information in snippets

### Step 3: Test Answer Quality

```bash
curl -X POST http://localhost:5200/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"summarise the UoI vs Dinshaw Anklaesari case"}'
```

The improved system should now:
- ✅ Include Supreme Court judgment (not claim it's missing)
- ✅ Use correct dates (1968 not 1891)
- ✅ Cover all parties and legal issues
- ✅ Explain the ruling and outcome
- ✅ Provide 800+ words for complex cases

---

## If Summaries Are Still Incomplete

### Problem: Still getting vague answers

**Solution 1: Increase top-k**
```bash
curl -X PUT http://localhost:5200/settings \
  -H 'Content-Type: application/json' \
  -d '{"retriever_top_k":12}'
```

**Solution 2: Increase context and prediction tokens**
```bash
curl -X PUT http://localhost:5200/settings \
  -H 'Content-Type: application/json' \
  -d '{"ollama_num_ctx":16384,"ollama_num_predict":3000}'
```

**Solution 3: Check what's being retrieved**
```bash
curl -X POST http://localhost:5200/debug/retrieve-mmr \
  -H 'Content-Type: application/json' \
  -d '{"question":"your question","lambda_mult":0.5}'
```

### Problem: Model keeps hallucinating

**This means retrieval is good but the LLM needs better grounding.**

Try these in order:
1. Lower temperature (less creative synthesis):
```bash
curl -X PUT http://localhost:5200/settings \
  -H 'Content-Type: application/json' \
  -d '{"llm_temperature":0}'
```

2. If that doesn't help, the embedding model may need tuning. Try:
```bash
# In .env, change:
EMBEDDING_MODEL=nomic-embed-text:latest
# Then re-ingest
```

3. If still having issues, try a larger LLM (if your GPU can handle it):
```bash
# In .env, change:
LLM_MODEL=llama2:13b
# Note: May require more VRAM
```

---

## Performance Tuning Guide

### For Cases with Lots of Context (Legal Briefs, Judgments)

```env
RETRIEVER_TOP_K=12           # Get more chunks
INGEST_CHUNK_SIZE=600        # Smaller chunks = more pieces to work with
INGEST_CHUNK_OVERLAP=300     # Higher overlap for context continuity
OLLAMA_NUM_CTX=16384         # Bigger context window
OLLAMA_NUM_PREDICT=4096      # Longer answers
LLM_TEMPERATURE=0.1          # Slight synthesis allowed
```

### For Quick Factual Answers (Case Names, Dates)

```env
RETRIEVER_TOP_K=5            # Fewer, focused chunks
INGEST_CHUNK_SIZE=1000       # Larger chunks
INGEST_CHUNK_OVERLAP=150     # Less overlap
OLLAMA_NUM_CTX=4096          # Standard context
OLLAMA_NUM_PREDICT=512       # Short answers
LLM_TEMPERATURE=0            # Strict factual grounding
```

### For Speed (If System is Slow)

```env
RETRIEVER_TOP_K=3            # Fewer chunks to process
INGEST_CHUNK_SIZE=1200       # Larger chunks = fewer to process
INGEST_CHUNK_OVERLAP=100     # Less redundancy
INGEST_EMBED_BATCH_SIZE=64   # Batch more chunks (if GPU allows)
OLLAMA_NUM_CTX=4096          # Don't bloat context window
OLLAMA_NUM_PREDICT=1024      # Moderate answer length
```

---

## Diagnostic Commands

### Check if embeddings are working
```bash
curl http://localhost:5200/settings | jq '.embedding_model, .embedding_provider'
```

### Verify retrieval quality score
```bash
curl -X POST http://localhost:5200/debug/retrieve-threshold \
  -H 'Content-Type: application/json' \
  -d '{"question":"your query","threshold":0.5}' | jq '.retrieved_count'
```

### Check current LLM model and settings
```bash
curl http://localhost:5200/settings | jq '.llm_model, .llm_temperature, .ollama_num_ctx, .ollama_num_predict'
```

### Measure retrieval diversity (MMR)
```bash
curl -X POST http://localhost:5200/debug/retrieve-mmr \
  -H 'Content-Type: application/json' \
  -d '{"question":"your query","lambda_mult":0.5}'
```

---

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "Insufficient evidence" for a single PDF | Embedding model too weak | Switch to `mxbai-embed-large`, re-ingest |
| Wrong case retrieved | Chunk boundaries broken | Lower chunk size (800 instead of 1000) |
| Answer is too short | Not enough context tokens | Increase `OLLAMA_NUM_PREDICT` to 2048+ |
| Model hallucinates dates | Temperature too high | Set `LLM_TEMPERATURE=0` or `0.05` |
| Summaries skip the ending | Context window too small | Increase `OLLAMA_NUM_CTX` to 8192+ |
| "Model not found" error | Wrong model name | Check `LLM_MODEL` in settings; run `ollama pull <model>` |
| Very slow ingestion | Too many workers on GPU | Set `INGEST_MAX_WORKERS=1` |

---

## Validation Test Cases

### Test 1: Single PDF Case Summary

**Query**: "summarise the UoI vs Dinshaw Anklaesari case"

**Expected Output Should Include**:
- [ ] Property details (GLR Survey No. 258)
- [ ] Timeline with exact dates/years
- [ ] All parties (UoI, Dinshaw Anklaesari, etc.)
- [ ] Legal issues (ownership, tenure, grant conditions)
- [ ] Supreme Court judgment
- [ ] Final ruling (UoI won, respondent's suit dismissed)
- [ ] No hallucinations about missing documents

**Length**: 800+ words for comprehensive summary

### Test 2: Cross-Reference Check

**Query**: "What did the Supreme Court rule?"

After: "summarise the UoI vs Dinshaw Anklaesari case"

**Expected**: Answer should reference the Supreme Court judgment from the case (not a different case)

### Test 3: Exact Fact Retrieval

**Query**: "What year was the sale registered?"

**Expected Answer**: Should include both:
- The year mentioned in original context (1968)
- NOT claim the date is missing
- Provide exact page reference

---

## Next Steps for Further Optimization

1. **Custom Legal Domain Embeddings**: Fine-tune embeddings on DEO legal documents
2. **Semantic Caching**: Cache embeddings of frequently asked questions
3. **Hierarchical Chunking**: Group chunks by case section (background, ruling, etc.)
4. **Multi-Agent Retrieval**: Have one agent find the case, another extract specific details
5. **Citation Tracking**: Automatically cross-reference related cases

---

## Support Notes

- **Hardware**: Tested on NVIDIA T1000 (4GB VRAM)
- **Model**: Qwen2.5:7b-instruct-q4_K_M
- **Embedding**: mxbai-embed-large:latest
- **Database**: PostgreSQL with PGVector
- **Tested**: Legal case summaries up to 5000 words
