# Quick Start: Validating the RAG Refinements

## Prerequisites

Before running tests, ensure:
1. PostgreSQL database is running and accessible
2. Ollama service is running (if using ollama for LLM/embeddings)
3. Backend dependencies are installed
4. Documents have been ingested into vectorstore

## Step 1: Verify Changes in Code

### Quick Syntax Check
```bash
cd /home/ashok/Desktop/RAGSYSTEM/deo-rag/backend
python -m py_compile config.py rag_pipeline.py app.py test_regression.py
# Should complete without errors
```

### Review Key Changes
```bash
# View updated prompt (should be simpler, no "FINAL ANSWER" marker)
grep -A 20 "template=" backend/rag_pipeline.py | head -20

# View increased token budget
grep "ollama_num_predict" backend/config.py

# View debug metadata addition
grep -A 5 "debug_flags = {" backend/app.py
```

## Step 2: Start Backend Server

```bash
cd /home/ashok/Desktop/RAGSYSTEM/deo-rag

# Activate virtual environment (if not already active)
source /home/ashok/Desktop/RAGSYSTEM/.venv/bin/activate

# Start the backend
python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

## Step 3: Run Regression Tests

In another terminal:

```bash
cd /home/ashok/Desktop/RAGSYSTEM/deo-rag

# Activate virtual environment
source /home/ashok/Desktop/RAGSYSTEM/.venv/bin/activate

# Run regression tests with default settings
python -m backend.test_regression

# Or with custom output path
python -m backend.test_regression --output test_results_$(date +%Y%m%d_%H%M%S).json
```

## Step 4: Manual Testing

Test a few questions manually to verify behavior:

```bash
# Test 1: Simple factual question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is estate records?"}'

# Response should include:
# - answer: Non-empty answer about estate records
# - sources: List of source documents
# - debug: Object with metrics
```

### Expected Response Format
```json
{
  "answer": "Estate Records is a chronic...",
  "sources": [
    {
      "source": "file.pdf",
      "page": 5
    }
  ],
  "debug": {
    "used_fallback": false,
    "used_rescue": false,
    "used_incomplete_detection": false,
    "answer_length": 245,
    "retrieved_count": 3,
    "top_similarity_score": 0.8421
  }
}
```

## Step 5: Review Test Results

### View Summary
```bash
# Pretty-print the JSON results
python -c "import json; r=json.load(open('test_results.json')); 
print('Success Rate:', r['summary']['successful_tests'], '/', r['summary']['total_tests']);
print('Metrics:', json.dumps(r['summary']['metrics'], indent=2))"
```

### Key Metrics to Check
- **False No-Info Responses**: Should be 0
- **Label Leakage**: Should be 0
- **Truncated Answers**: Should be low (< 2 for 10 tests)
- **Avg Quality Score**: Should be > 80
- **Fallback Usage**: Shows how often simpler prompt was needed
- **Rescue Usage**: Shows how often extractive rescue was used

## Step 6: Visual Inspection

### Check for Label Leakage
```bash
# Extract all answers and search for leaked labels
python -c "
import json
results = json.load(open('test_results.json'))['summary']['results']
leaked = []
for r in results:
    if 'STRUCTURED' in r.get('answer', '') or 'FACT/SHORT' in r.get('answer', ''):
        leaked.append(r)
print(f'Found {len(leaked)} answers with leaked labels')
for r in leaked[:3]:
    print(f\"  - Q: {r['question'][:50]}...\")
"
```

### Check Answer Completeness
```bash
# Look for potentially truncated answers
python -c "
import json
results = json.load(open('test_results.json'))['summary']['results']
short = []
for r in results:
    qa = r.get('quality_analysis', {})
    if qa.get('is_truncated'):
        short.append(r)
print(f'Found {len(short)} truncated answers')
for r in short[:3]:
    print(f\"  - Q: {r['question']}\")
    print(f\"    A: {r['answer'][:100]}...\")
    print()
"
```

## Troubleshooting

### Backend Won't Start
```bash
# Check for import errors
python -c "import backend.app"

# Check database connection
python -c "from backend.config import SETTINGS; print(SETTINGS.database_url)"

# Check if port 8000 is in use
lsof -i :8000
```

### Regression Tests Time Out
- Increase `--timeout` parameter (default 60s)
- Check if backend is responding: `curl http://localhost:8000/health`
- Check if documents are ingested: `curl http://localhost:8000/documents`

### Answers Still Truncated
- Check `ollama_num_predict` value in config.py (should be 768+)
- Check Ollama model is capable of generation
- Review test_results.json for which paths were used

### Getting "Could Not Connect" Error
- Verify backend is running on http://localhost:8000
- Check firewall/network settings
- Verify base URL in regression test command

## Advanced Validation

### Test Specific Question Type
```bash
# Test a complex descriptive question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the stages and management of estate-record retinopathy?"}'
```

### Debug Retrieval Process
```bash
# See what chunks are being retrieved
curl -X POST http://localhost:8000/debug/retrieve \
  -H "Content-Type: application/json" \
  -d '{"question": "What is estate records?"}'

# See with similarity threshold
curl -X POST "http://localhost:8000/debug/retrieve-threshold?threshold=0.7" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is estate records?"}'

# See with MMR (Maximal Marginal Relevance)
curl -X POST "http://localhost:8000/debug/retrieve-mmr?lambda_mult=0.5" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is estate records?"}'
```

## Success Criteria

Implementation is successful when:

✅ Backend starts without errors  
✅ Regression tests run to completion  
✅ False no-info responses = 0 (when sources exist)  
✅ Label leakage instances = 0  
✅ Average quality score > 80/100  
✅ Descriptive answers are not truncated  
✅ Debug metadata is included in responses  
✅ Fallback/rescue paths activate as needed  

## Next: Compare Results Over Time

```bash
# Save baseline results
cp test_results.json test_results_baseline.json

# Run again later
python -m backend.test_regression --output test_results_latest.json

# Compare metrics
python -c "
import json
baseline = json.load(open('test_results_baseline.json'))['summary']['metrics']
latest = json.load(open('test_results_latest.json'))['summary']['metrics']

for key in baseline:
    b_val = baseline[key]
    l_val = latest[key]
    if isinstance(b_val, (int, float)):
        delta = l_val - b_val
        pct = (delta / b_val * 100) if b_val != 0 else 0
        print(f'{key}: {b_val} → {l_val} ({delta:+.0f}, {pct:+.1f}%)')
"
```

## Contact & Support

For issues:
1. Check IMPLEMENTATION_SUMMARY.md for detailed changes
2. Review refining.md for original requirements
3. Check backend logs for error messages
4. Verify all services are running
