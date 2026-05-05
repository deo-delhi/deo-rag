import os
import time
import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any

def run_subprocess_bench(config_name: str, env_vars: Dict[str, str]):
    print(f"\n>>> Starting Subprocess for: {config_name}")
    
    script_code = f"""
import os
import time
import json
import sys
from pathlib import Path

# Add the directory containing 'backend' to path
# Backend is at /home/assassin/code/deo-rag/deo-rag/backend/
sys.path.append('/home/assassin/code/deo-rag/deo-rag')

# Ensure env vars are set BEFORE any imports that might use them
env_vars = {json.dumps(env_vars)}
for k, v in env_vars.items():
    os.environ[k] = v

from backend.rag_pipeline import build_qa_chain
import torch

def get_vram():
    if torch.cuda.is_available():
        return torch.cuda.memory_reserved(0) / 1024 / 1024
    return 0

queries = [
    "What is the site address and GLR Survey No. mentioned in the notice dated 14th December, 2001 in the Usha Kapoor case?",
    "Who are the appellants in Civil Appeal No. 1844 of 2008?",
    "Which Governor General-in-Council Order was cited in the resumption notice in the Usha Kapoor judgment?"
]

start_vram = get_vram()
qa_chain = build_qa_chain(collection_name="test_ingest_bench", use_mmr=True)

results = []
total_time = 0

for q in queries:
    start_time = time.time()
    response = qa_chain.invoke({{"query": q}})
    elapsed = time.time() - start_time
    total_time += elapsed
    results.append({{"query": q, "answer": response["result"], "time": elapsed}})

peak_vram = get_vram()

print(json.dumps({{
    "config": "{config_name}",
    "total_time": total_time,
    "avg_time": total_time / len(queries),
    "peak_vram": peak_vram,
    "results": results
}}))
"""
    
    env = os.environ.copy()
    env.update(env_vars)
    
    # Run using the experimental venv python
    python_exe = "/home/assassin/code/deo-rag/experimental_vram_env/bin/python"
    
    result = subprocess.run(
        [python_exe, "-c", script_code],
        capture_output=True,
        text=True,
        env=env
    )
    
    if result.returncode != 0:
        print(f"  Error in {config_name}: {result.stderr}")
        return {"config": config_name, "error": result.stderr}
    
    try:
        # Find the JSON line in output
        for line in result.stdout.splitlines():
            if line.startswith('{"config"'):
                return json.loads(line)
    except:
        print(f"  Failed to parse JSON from: {result.stdout}")
        return {"config": config_name, "error": "JSON parse error"}

def main():
    # 1. Current Default
    current_vars = {
        "EMBEDDING_PROVIDER": "ollama",
        "EMBEDDING_MODEL": "mxbai-embed-large:latest",
        "LLM_MODEL": "llama3.2:latest",
        "CHROMA_PERSIST_DIRECTORY": "/home/assassin/code/deo-rag/vectorstore/chroma_db"
    }
    
    # 2. Recommended Setup
    rec_vars = {
        "EMBEDDING_PROVIDER": "huggingface",
        "EMBEDDING_MODEL": "BAAI/bge-small-en",
        "LLM_MODEL": "llama3.2:latest",
        "CHROMA_PERSIST_DIRECTORY": "/home/assassin/code/deo-rag/vectorstore/chroma_db"
    }
    
    bench_results = []
    
    # Run Current
    bench_results.append(run_subprocess_bench("Current Defaults (Ollama + Ollama)", current_vars))
    
    # Run Recommended
    bench_results.append(run_subprocess_bench("Recommended (Ollama + HuggingFace)", rec_vars))
    
    print("\n" + "="*50)
    print("FINAL COMPARISON")
    print("="*50)
    for r in bench_results:
        if not r or "error" in r:
            print(f"\nConfig: {r.get('config', 'Unknown')} - FAILED: {r.get('error', 'No result')}")
            continue
        print(f"\nConfig: {r['config']}")
        print(f"  Total Time: {r['total_time']:.2f}s")
        print(f"  Avg Time/Query: {r['avg_time']:.2f}s")
        print(f"  Peak VRAM: {r['peak_vram']:.2f} MB")
        if r['results']:
            print(f"  Sample Answer (Q1): {r['results'][0]['answer'][:100]}...")

    with open("vram_benchmark_results.json", "w") as f:
        json.dump(bench_results, f, indent=2)

if __name__ == "__main__":
    main()
