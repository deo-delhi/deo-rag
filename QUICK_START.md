# Quick Start: Deploy RAG Improvements

## What Changed

### ✅ Configuration (.env)
- Embedding: `BAAI/bge-small-en` → `mxbai-embed-large:latest` (Ollama)
- Retrieval: `4` → `20` chunks
- Context: `4096` → `12288` tokens
- Generation: `512` → `3072` tokens
- Chunks: `1000` size, `200` overlap
- Temperature: `0` → `0.1`

### ✅ Prompts (rag_pipeline.py)
- Added structured case summary format
- Added synthesis rules to connect chunks
- Prevented false "insufficient information" abstentions

### ✅ Chunking (ingest.py)
- Respects legal document paragraph boundaries
- Better chunk coherence for complex cases

### ✅ Retrieval (rag_pipeline.py)
- Added query expansion for case name variations
- Better semantic matching for legal terminology

---

## 4-Step Deployment

### 1. Clear vectorstore (1 min)
```bash
curl -X POST http://localhost:5200/data/clear \
  -H 'Content-Type: application/json' \
  -d '{"delete_files":false,"delete_vectorstore":true}'
```

### 2. Restart backend (2 min)
```bash
docker-compose down
docker-compose up -d
```

### 3. Re-ingest documents (5-10 min, depends on document size)
```bash
curl -X POST http://localhost:5200/ingest/start \
  -H 'Content-Type: application/json' \
  -d '{"chunk_size":800,"chunk_overlap":250}'

# Wait for completion
curl http://localhost:5200/ingest/status
```

### 4. Test improvements (1 min)
```bash
# Run validation
python /home/ashok/Documents/ritik/code/deo-rag/validation.py

# Or test a case manually
curl -X POST http://localhost:5200/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"summarise the UoI vs Dinshaw Anklaesari case"}'
```

---

## Expected Improvement

| What | Before | After |
|------|--------|-------|
| Missing judgments | ❌ Claims missing | ✅ Includes full ruling |
| Timeline accuracy | ❌ Wrong dates | ✅ Accurate dates |
| Completeness | ❌ 300 words | ✅ 1000+ words |
| Hallucinations | ❌ Common | ✅ Rare |

---

## If Things Don't Improve

### Problem: Still incomplete
```bash
# Increase chunks retrieved
curl -X PUT http://localhost:5200/settings \
  -H 'Content-Type: application/json' \
  -d '{"retriever_top_k":12}'
```

### Problem: Wrong information
```bash
# Reduce temperature
curl -X PUT http://localhost:5200/settings \
  -H 'Content-Type: application/json' \
  -d '{"llm_temperature":0}'
```

### Problem: Can't find the document
```bash
# Check retrieval quality
curl -X POST http://localhost:5200/debug/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"question":"your query"}'
```

---

## Files Modified

✅ `.env` - Optimized parameters  
✅ `backend/config.py` - New defaults  
✅ `backend/rag_pipeline.py` - Better prompts, query expansion  
✅ `backend/ingest.py` - Legal-aware chunking  
✅ `RAG_IMPROVEMENTS_GUIDE.md` - Full documentation  
✅ `IMPROVEMENTS_SUMMARY.md` - Detailed report  
✅ `validation.py` - Test script  

---

## Key Files to Read

1. **[IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md)** - What was wrong, what's fixed, why
2. **[RAG_IMPROVEMENTS_GUIDE.md](RAG_IMPROVEMENTS_GUIDE.md)** - Troubleshooting & tuning
3. **validation.py** - How to validate the improvements

---

## Support

- **Questions?** Check [RAG_IMPROVEMENTS_GUIDE.md](RAG_IMPROVEMENTS_GUIDE.md)
- **Still not working?** Run `validation.py` to diagnose
- **Need more detail?** See [IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md)
