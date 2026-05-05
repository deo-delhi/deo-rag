import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent / "deo-rag"))

from backend.rag_pipeline import build_qa_chain

def main():
    print("Testing accuracy on Usha Kapoor vs GoI.pdf...")
    
    qa_chain = build_qa_chain(
        collection_name="test_ingest_bench",
        use_mmr=True
    )
    
    query = "What is the site address and GLR Survey No. mentioned in the notice dated 14th December, 2001 in the Usha Kapoor case?"
    
    print(f"Query: {query}")
    response = qa_chain.invoke({"query": query})
    
    print("\n--- Accuracy Test Result ---")
    print(f"Answer: {response['result']}")
    print("\nSources:")
    for doc in response['source_documents']:
        print(f"- {doc.metadata.get('source')} (page {doc.metadata.get('page')})")

if __name__ == "__main__":
    main()
