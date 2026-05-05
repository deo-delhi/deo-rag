import time
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent / "deo-rag"))

from backend.ingest import ingest

def main():
    start_time = time.time()
    print("Starting ingestion of 13 files...")
    
    result = ingest(
        replace_collection=True,
        collection_name="test_ingest_bench",
        library="unflagged"
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n--- Ingestion Bench Results ---")
    print(f"Total time: {duration:.2f} seconds")
    print(f"Scanned files: {result.scanned_files}")
    print(f"Parsed documents: {result.parsed_documents}")
    print(f"Chunks created: {result.chunks_created}")
    print(f"Failed files: {result.failed_files}")

if __name__ == "__main__":
    main()
