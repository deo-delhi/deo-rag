#!/usr/bin/env python3
"""
RAG System Validation Script
Tests the improved DEO RAG system against known case summaries.
"""

import json
import requests
import sys
from typing import Dict, List, Tuple

# Configuration
BASE_URL = "http://localhost:5200"
TIMEOUT = 600

# Test cases with expected content
TEST_CASES = [
    {
        "name": "UoI vs Dinshaw Anklaesari",
        "query": "summarise the UoI vs Dinshaw Anklaesari case",
        "expected_elements": [
            "Union of India",
            "Dinshaw",
            "Anklaesari",
            "Supreme Court",
            "GLR Survey",
            "Elphinstone Road",
            "1968",
            "judgment",
            "ruling",
            "property",
        ],
        "should_not_contain": [
            "insufficient information",
            "further details",
            "more information",
            "the document does not contain",
        ],
        "min_length": 500,
    },
    {
        "name": "Legal case property details",
        "query": "What are the details of the property involved in the Dinshaw case?",
        "expected_elements": [
            "property",
            "land",
            "survey",
            "Pune",
            "Cantonment",
        ],
        "should_not_contain": [
            "insufficient",
        ],
        "min_length": 200,
    },
]


def check_health() -> bool:
    """Check if backend is running."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Backend health check failed: {e}")
        return False


def get_settings() -> Dict:
    """Fetch current settings."""
    try:
        response = requests.get(f"{BASE_URL}/settings", timeout=5)
        return response.json()
    except Exception as e:
        print(f"❌ Failed to get settings: {e}")
        return {}


def check_retrieval_quality(query: str) -> Tuple[int, float]:
    """
    Check retrieval quality for a query.
    Returns: (retrieved_count, avg_score)
    """
    try:
        response = requests.post(
            f"{BASE_URL}/debug/retrieve",
            json={"question": query},
            timeout=TIMEOUT,
        )
        data = response.json()
        documents = data.get("documents", [])
        
        if not documents:
            return 0, 0.0
        
        avg_score = sum(doc["similarity_score"] for doc in documents) / len(documents)
        return len(documents), avg_score
    except Exception as e:
        print(f"❌ Retrieval check failed: {e}")
        return 0, 0.0


def ask_question(query: str) -> str:
    """Ask a question and get the answer."""
    try:
        response = requests.post(
            f"{BASE_URL}/ask",
            json={"question": query},
            timeout=TIMEOUT,
        )
        data = response.json()
        return data.get("answer", "")
    except Exception as e:
        print(f"❌ Failed to ask question: {e}")
        return ""


def validate_answer(answer: str, test_case: Dict) -> Dict:
    """Validate an answer against expected elements."""
    results = {
        "passed": True,
        "issues": [],
        "coverage": 0,
        "found_elements": [],
        "missing_elements": [],
    }
    
    # Check length
    if len(answer) < test_case["min_length"]:
        results["passed"] = False
        results["issues"].append(
            f"Answer too short ({len(answer)} chars, expected {test_case['min_length']}+)"
        )
    
    # Check for expected elements
    answer_lower = answer.lower()
    for element in test_case["expected_elements"]:
        if element.lower() in answer_lower:
            results["found_elements"].append(element)
        else:
            results["missing_elements"].append(element)
            results["passed"] = False
    
    # Check for things that shouldn't be there
    for forbidden in test_case["should_not_contain"]:
        if forbidden.lower() in answer_lower:
            results["passed"] = False
            results["issues"].append(f"Found forbidden phrase: '{forbidden}'")
    
    # Calculate coverage percentage
    if test_case["expected_elements"]:
        results["coverage"] = (
            len(results["found_elements"]) / len(test_case["expected_elements"]) * 100
        )
    
    return results


def run_validation():
    """Run the complete validation suite."""
    print("=" * 70)
    print("DEO RAG SYSTEM VALIDATION")
    print("=" * 70)
    
    # Check health
    print("\n1. Backend Health Check...")
    if not check_health():
        print("❌ Backend is not running. Start it with: docker-compose up")
        return False
    print("✅ Backend is running")
    
    # Show settings
    print("\n2. Current Configuration...")
    settings = get_settings()
    print(f"   LLM Model: {settings.get('llm_model')}")
    print(f"   LLM Temperature: {settings.get('llm_temperature')}")
    print(f"   Embedding Model: {settings.get('embedding_model')}")
    print(f"   Retriever Top-K: {settings.get('retriever_top_k')}")
    print(f"   Context Window: {settings.get('ollama_num_ctx')}")
    print(f"   Max Tokens: {settings.get('ollama_num_predict')}")
    
    # Run test cases
    print("\n3. Running Test Cases...\n")
    
    all_passed = True
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"Test {i}: {test_case['name']}")
        print(f"Query: {test_case['query']}")
        
        # Check retrieval
        ret_count, avg_score = check_retrieval_quality(test_case["query"])
        print(f"  Retrieval: {ret_count} chunks, avg score: {avg_score:.4f}")
        
        if ret_count == 0:
            print("  ⚠️  No chunks retrieved!")
            all_passed = False
            continue
        
        if avg_score < 0.3:
            print(f"  ⚠️  Low retrieval scores (< 0.3)")
        elif avg_score >= 0.5:
            print(f"  ✅ Good retrieval scores (>= 0.5)")
        
        # Ask question
        answer = ask_question(test_case["query"])
        if not answer:
            print("  ❌ No answer received")
            all_passed = False
            continue
        
        # Validate answer
        validation = validate_answer(answer, test_case)
        
        print(f"  Answer Length: {len(answer)} chars")
        print(f"  Content Coverage: {validation['coverage']:.1f}%")
        
        if validation["found_elements"]:
            print(f"  ✅ Found: {', '.join(validation['found_elements'][:5])}")
        
        if validation["missing_elements"]:
            print(f"  ❌ Missing: {', '.join(validation['missing_elements'][:5])}")
        
        if validation["issues"]:
            for issue in validation["issues"]:
                print(f"  ⚠️  {issue}")
        
        if validation["passed"]:
            print("  ✅ PASSED")
        else:
            print("  ❌ FAILED")
            all_passed = False
        
        print()
    
    # Summary
    print("=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("\nThe RAG system is working correctly!")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        print("\nConsider:")
        print("- Re-ingesting with new parameters")
        print("- Checking retrieval quality with /debug/retrieve endpoint")
        print("- Increasing RETRIEVER_TOP_K if summaries are incomplete")
        print("- Checking that PDF is in the correct knowledge base")
        return False


def print_usage():
    """Print usage instructions."""
    print("""
Usage: python validation.py [options]

Options:
  --help              Show this help message
  --query TEXT        Run a single query (for manual testing)
  --debug             Show detailed retrieval information

Examples:
  python validation.py
  python validation.py --query "summarise the case"
  python validation.py --debug
""")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print_usage()
            sys.exit(0)
        elif sys.argv[1] == "--query" and len(sys.argv) > 2:
            query = " ".join(sys.argv[2:])
            answer = ask_question(query)
            print(f"Query: {query}\n")
            print(f"Answer:\n{answer}")
            sys.exit(0)
        elif sys.argv[1] == "--debug":
            query = sys.argv[2] if len(sys.argv) > 2 else "summarise the UoI vs Dinshaw Anklaesari case"
            ret_count, avg_score = check_retrieval_quality(query)
            print(f"Query: {query}")
            print(f"Retrieved chunks: {ret_count}, avg score: {avg_score:.4f}")
            sys.exit(0)
    
    success = run_validation()
    sys.exit(0 if success else 1)
