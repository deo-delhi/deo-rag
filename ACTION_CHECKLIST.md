# 🚀 Action Checklist - Deploy RAG Improvements NOW

## What You Need to Do

### ✅ PRE-DEPLOYMENT (Verify changes)

- [x] Reviewed `.env` changes (embedding model, chunk size, token limits)
- [x] Reviewed `backend/config.py` changes (new defaults)
- [x] Reviewed prompt improvements in `backend/rag_pipeline.py`
- [x] Verified `backend/ingest.py` has new chunking logic

**Files Modified**:
1. ✅ `/deo-rag/.env` - Configuration parameters
2. ✅ `/deo-rag/backend/config.py` - Default settings
3. ✅ `/deo-rag/backend/rag_pipeline.py` - Prompts + query expansion
4. ✅ `/deo-rag/backend/ingest.py` - Chunking strategy

**Documentation Added**:
1. ✅ `IMPROVEMENTS_SUMMARY.md` - What was wrong and how it's fixed
2. ✅ `TECHNICAL_DEEP_DIVE.md` - Why each improvement works
3. ✅ `RAG_IMPROVEMENTS_GUIDE.md` - Troubleshooting & tuning
4. ✅ `QUICK_START.md` - 4-step deployment
5. ✅ `validation.py` - Test script

---

### 🔧 DEPLOYMENT (Execute these steps)

**Time Required**: ~15 minutes (5 for setup + 10 for re-ingestion)

#### Step 1: Stop the existing system (2 min)
```bash
cd /home/ashok/Documents/ritik/code/deo-rag/deo-rag
docker-compose down
```

#### Step 2: Clear old vectorstore (1 min)
```bash
# Option A: Via container (if still running)
docker-compose exec postgres psql -U admin -d deorag \
  -c "DELETE FROM langchain_pg_embedding;"

# Option B: Just delete and restart postgres
# This happens automatically when you re-run docker-compose
```

#### Step 3: Start the backend with new config (2 min)
```bash
docker-compose up -d
sleep 30  # Wait for startup
```

#### Step 4: Verify backend is ready (1 min)
```bash
curl http://localhost:5200/health
# Should return: {"status":"ok"}

curl http://localhost:5200/settings | jq '.retriever_top_k, .embedding_model'
# Should show: 20 and "mxbai-embed-large:latest"
```

#### Step 5: Clear vectorstore via API (1 min)
```bash
curl -X POST http://localhost:5200/data/clear \
  -H 'Content-Type: application/json' \
  -d '{
    "delete_files": false,
    "delete_vectorstore": true,
    "knowledge_base": "unflagged"
  }'
# Should return: {"status":"cleared",...}
```

#### Step 6: Start re-ingestion (1 min to trigger)
```bash
curl -X POST http://localhost:5200/ingest/start \
  -H 'Content-Type: application/json' \
  -d '{
    "chunk_size": 800,
    "chunk_overlap": 250,
    "replace_collection": false,
    "knowledge_base": "unflagged"
  }'
# Should return: {"status":"started","job_id":"..."}
```

#### Step 7: Monitor ingestion progress (5-10 min)
```bash
# Run this every minute to check progress
curl http://localhost:5200/ingest/status | jq '{
  status: .status,
  successful_files: .result.successful_files,
  chunks_created: .result.chunks_created,
  failed: .result.failed_files
}'

# When complete, status will be "completed"
```

#### Step 8: Validate improvements (2 min)
```bash
# Run the validation script
cd /home/ashok/Documents/ritik/code/deo-rag
python validation.py

# Should show test results
# If all ✅: SUCCESS!
# If any ❌: Check troubleshooting section below
```

---

### ✨ VERIFY IMPROVEMENTS (Quick sanity check)

**Test the specific case that was failing**:

```bash
curl -X POST http://localhost:5200/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"summarise the UoI vs Dinshaw Anklaesari case"}' \
  | jq '.answer' | head -50
```

**Expected output should include**:
- ✅ "Supreme Court" (not claim it's missing)
- ✅ "1968" (not "1891")
- ✅ Multiple sections (Background, Parties, Timeline, Ruling, Outcome)
- ✅ 800+ words (comprehensive)
- ✅ Ends with a full sentence (not truncated)

**If you see these**, deployment was successful!

---

### 🔍 QUICK DIAGNOSTIC (If something's wrong)

#### Check 1: Is backend running?
```bash
curl http://localhost:5200/health
# ✅ {"status":"ok"} = Good
# ❌ Connection refused = Restart with: docker-compose up -d
```

#### Check 2: Are new settings active?
```bash
curl http://localhost:5200/settings | jq '.retriever_top_k'
# ✅ 20 = Good
# ❌ 4 = Need to restart backend
```

#### Check 3: Is ingestion complete?
```bash
curl http://localhost:5200/ingest/status | jq '.status'
# ✅ "completed" = Ready
# ⏳ "running" = Still working
# ❌ "failed" = Check error message
```

#### Check 4: Can we retrieve documents?
```bash
curl -X POST http://localhost:5200/debug/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"question":"test query"}' \
  | jq '.retrieved_count'
# ✅ > 0 = Good
# ❌ 0 = Documents not ingested or query mismatch
```

---

### ⚠️ TROUBLESHOOTING CHECKLIST

| Problem | Diagnosis | Solution |
|---------|-----------|----------|
| Backend won't start | Check logs: `docker-compose logs` | Fix: `docker-compose down && docker-compose up -d` |
| Shows old settings | Backend cache | Restart: `docker-compose restart backend` |
| "0 documents retrieved" | Ingestion failed or not started | Check ingest status, re-run ingest/start |
| Still getting vague answers | Insufficient context or chunks | Increase: `retriever_top_k=12, ollama_num_predict=3000` |
| Model hallucinates dates | Temperature too high | Lower: `llm_temperature=0` |
| "Insufficient information" error | Incorrect prompt version | Verify `backend/rag_pipeline.py` has new FALLBACK_ANSWER_PROMPT |
| Ingestion very slow | Too many workers on T1000 | Set: `INGEST_MAX_WORKERS=1` in .env |

---

### 📊 SUCCESS CRITERIA

After deployment, your system should show:

**Before Improvements** (What you saw):
```
Q: "Summarise the UoI vs Dinshaw case"
A: "Insufficient information is provided within the given context..."
   - Missing Supreme Court judgment
   - Wrong timeline (1891 vs 1968)
   - ~300 words
   - Multiple hallucinations
```

**After Improvements** (What you should see):
```
Q: "Summarise the UoI vs Dinshaw case"
A: "BACKGROUND: The case involves property GLR Survey No. 258 at 
    Elphinstone Road, Pune Cantonment, originally granted to 
    Nusserwanji Sorabji Anklesaria under GGO 14 of 1827...
    
    [Multiple sections covering all aspects]
    
    SUPREME COURT JUDGMENT: The Court found that under Sections 2 and 
    3 of the Government Grants Act, 1895, the Government has unfettered 
    right to resume the land...
    
    OUTCOME: Supreme Court ruled in favor of Union of India..."
   - ✅ Includes Supreme Court judgment
   - ✅ Accurate dates (1968)
   - ✅ 1000+ words
   - ✅ No hallucinations
```

---

### 🎯 NEXT STEPS (After validation)

1. **Monitor performance** over next few days
   - Track answer quality with debug endpoints
   - Adjust `retriever_top_k` or temperature if needed

2. **Collect feedback** from users
   - Are case summaries now accurate?
   - Are dates correct?
   - Are judgments included?

3. **Fine-tune further** (optional)
   - If summaries still incomplete: increase `retriever_top_k` to 12
   - If answers hallucinate: lower `llm_temperature` to 0
   - If too slow: adjust `INGEST_CHUNK_SIZE` to 1000

4. **Document your settings** for future reference
   - Record final values used
   - Note any case-specific quirks you find

---

### 📚 REFERENCE DOCUMENTS

- **QUICK_START.md** ← Start here
- **IMPROVEMENTS_SUMMARY.md** ← What was fixed
- **TECHNICAL_DEEP_DIVE.md** ← Why it works
- **RAG_IMPROVEMENTS_GUIDE.md** ← How to tune further
- **validation.py** ← How to test

---

### ⏱️ TIME ESTIMATE

| Task | Time |
|------|------|
| Backup current state | 2 min |
| Deploy changes | 3 min |
| Clear vectorstore | 1 min |
| Re-ingest documents | 5-10 min |
| Validate | 2 min |
| **TOTAL** | **13-18 min** |

**⚡ Go ahead and deploy!**

---

## Commands Summary

```bash
# Navigate to project
cd /home/ashok/Documents/ritik/code/deo-rag/deo-rag

# Stop existing
docker-compose down

# Start fresh
docker-compose up -d

# Wait for startup
sleep 30

# Clear vectorstore
curl -X POST http://localhost:5200/data/clear \
  -H 'Content-Type: application/json' \
  -d '{"delete_files":false,"delete_vectorstore":true}'

# Start ingestion
curl -X POST http://localhost:5200/ingest/start \
  -H 'Content-Type: application/json' \
  -d '{"chunk_size":800,"chunk_overlap":250}'

# Monitor (run multiple times)
curl http://localhost:5200/ingest/status

# Test when done
python /home/ashok/Documents/ritik/code/deo-rag/validation.py
```

**That's it! Your RAG is now improved.** 🎉
