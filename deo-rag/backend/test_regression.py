"""
Regression testing framework for DEO RAG system.

This module tests the RAG system against a set of known questions and expected patterns,
tracking improvement over time. Metrics tracked include:
- False no-information responses
- Label leakage (STRUCTURED, FACT/SHORT, DESCRIPTIVE, Mode, Classification)
- Truncated/incomplete answers
- Unsupported answer drift
- Source utilization

Usage:
    python -m backend.test_regression [--output results.json] [--config test_cases.json]
"""

import json
import time
import argparse
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

import requests


class RegressionTester:
    """Test runner for RAG system regression testing."""

    LEAKED_LABELS = ("STRUCTURED", "FACT/SHORT", "DESCRIPTIVE", "Mode", "Classification")
    NO_INFO_RESPONSE = "The document does not contain this information."

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 60):
        """
        Initialize the tester.
        
        Args:
            base_url: Base URL of the RAG API (default: http://localhost:8000)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.results = []

    def check_label_leakage(self, answer: str) -> tuple[bool, Optional[str]]:
        """
        Check if answer contains leaked internal labels.
        
        Returns:
            (has_leakage, leaked_label or None)
        """
        for label in self.LEAKED_LABELS:
            if label in answer:
                return True, label
        return False, None

    def check_answer_quality(
        self,
        question: str,
        answer: str,
        expected_keywords: Optional[list[str]] = None,
    ) -> dict:
        """
        Analyze answer quality based on multiple criteria.
        
        Args:
            question: The question asked
            answer: The answer from the system
            expected_keywords: Optional list of keywords expected in good answers
            
        Returns:
            Quality analysis dictionary
        """
        quality = {
            "question": question,
            "answer_length": len(answer),
            "is_no_info_response": answer.strip() == self.NO_INFO_RESPONSE,
            "has_label_leakage": False,
            "leaked_label": None,
            "is_truncated": False,
            "missing_keywords": [],
            "quality_score": 100,  # Start perfect, deduct for issues
        }

        # Check label leakage
        has_leakage, label = self.check_label_leakage(answer)
        if has_leakage:
            quality["has_label_leakage"] = True
            quality["leaked_label"] = label
            quality["quality_score"] -= 50

        # Check for truncation (answer ends abruptly)
        if answer and answer.strip()[-1] not in {'.', '!', '?', ')', ']', '}'}:
            quality["is_truncated"] = True
            quality["quality_score"] -= 20

        # Check for very short answers relative to question complexity
        if len(question.split()) >= 7 and len(answer) < 260:
            quality["is_potentially_incomplete"] = True
            quality["quality_score"] -= 15

        # Check for expected keywords
        if expected_keywords:
            found_keywords = []
            for keyword in expected_keywords:
                if keyword.lower() in answer.lower():
                    found_keywords.append(keyword)
                else:
                    quality["missing_keywords"].append(keyword)
            
            # Deduct points for missing expected keywords
            if quality["missing_keywords"]:
                quality["quality_score"] -= len(quality["missing_keywords"]) * 5

        return quality

    def run_test_case(
        self,
        question: str,
        expected_keywords: Optional[list[str]] = None,
        should_have_answer: bool = True,
    ) -> dict:
        """
        Run a single test case.
        
        Args:
            question: The question to ask
            expected_keywords: Optional keywords expected in the answer
            should_have_answer: Whether this question should return information
            
        Returns:
            Test result dictionary
        """
        result = {
            "question": question,
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "response_time": 0,
            "answer": None,
            "sources_count": 0,
            "debug_info": {},
            "quality_analysis": {},
        }

        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/ask",
                json={"question": question},
                timeout=self.timeout,
            )
            result["response_time"] = time.time() - start_time

            if response.status_code != 200:
                result["error"] = f"HTTP {response.status_code}: {response.text}"
                return result

            data = response.json()
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            debug_info = data.get("debug", {})

            result["answer"] = answer
            result["sources_count"] = len(sources)
            result["debug_info"] = debug_info
            result["success"] = True

            # Analyze answer quality
            quality = self.check_answer_quality(
                question,
                answer,
                expected_keywords=expected_keywords,
            )
            result["quality_analysis"] = quality

            # Check expectations
            if should_have_answer and answer.strip() == self.NO_INFO_RESPONSE:
                result["quality_analysis"]["quality_score"] -= 30
                result["quality_analysis"]["unexpected_no_info"] = True

            return result

        except requests.exceptions.Timeout:
            result["error"] = "Request timed out"
            return result
        except requests.exceptions.ConnectionError:
            result["error"] = f"Could not connect to {self.base_url}"
            return result
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            return result

    def run_test_suite(self, test_cases: list[dict]) -> dict:
        """
        Run a suite of test cases.
        
        Args:
            test_cases: List of test case dictionaries with keys:
                - question (required)
                - expected_keywords (optional)
                - should_have_answer (optional, default True)
                
        Returns:
            Summary report
        """
        print(f"Running {len(test_cases)} test cases...")
        start_time = time.time()

        for i, test_case in enumerate(test_cases, 1):
            print(f"[{i}/{len(test_cases)}] {test_case['question'][:60]}...", end=" ", flush=True)
            result = self.run_test_case(
                question=test_case["question"],
                expected_keywords=test_case.get("expected_keywords"),
                should_have_answer=test_case.get("should_have_answer", True),
            )
            self.results.append(result)
            status = "✓" if result["success"] else "✗"
            print(status)

        total_time = time.time() - start_time

        # Generate summary
        summary = self._generate_summary(total_time)
        return summary

    def _generate_summary(self, total_time: float) -> dict:
        """Generate a summary report of all test results."""
        if not self.results:
            return {}

        summary = {
            "total_tests": len(self.results),
            "successful_tests": sum(1 for r in self.results if r["success"]),
            "failed_tests": sum(1 for r in self.results if not r["success"]),
            "total_time_seconds": total_time,
            "metrics": {
                "false_no_info_responses": 0,
                "label_leakage_count": 0,
                "truncated_answers": 0,
                "incomplete_answers": 0,
                "used_fallback": 0,
                "used_rescue": 0,
                "used_incomplete_detection": 0,
                "avg_answer_length": 0,
                "avg_response_time": 0,
                "avg_sources_retrieved": 0,
            },
            "quality_scores": [],
            "results": self.results,
        }

        # Calculate metrics
        answers = []
        response_times = []
        sources_counts = []
        quality_scores = []

        for result in self.results:
            if not result["success"]:
                continue

            quality = result.get("quality_analysis", {})
            debug_info = result.get("debug_info", {})

            # Count issues
            if quality.get("is_no_info_response"):
                if quality.get("unexpected_no_info"):
                    summary["metrics"]["false_no_info_responses"] += 1
            
            if quality.get("has_label_leakage"):
                summary["metrics"]["label_leakage_count"] += 1

            if quality.get("is_truncated"):
                summary["metrics"]["truncated_answers"] += 1

            if quality.get("is_potentially_incomplete"):
                summary["metrics"]["incomplete_answers"] += 1

            # Track debug paths
            if debug_info.get("used_fallback"):
                summary["metrics"]["used_fallback"] += 1
            if debug_info.get("used_rescue"):
                summary["metrics"]["used_rescue"] += 1
            if debug_info.get("used_incomplete_detection"):
                summary["metrics"]["used_incomplete_detection"] += 1

            # Collect data for averages
            answers.append(result.get("answer", ""))
            response_times.append(result.get("response_time", 0))
            sources_counts.append(result.get("sources_count", 0))
            quality_scores.append(quality.get("quality_score", 0))

        # Calculate averages
        if answers:
            summary["metrics"]["avg_answer_length"] = sum(len(a) for a in answers) / len(answers)
        if response_times:
            summary["metrics"]["avg_response_time"] = sum(response_times) / len(response_times)
        if sources_counts:
            summary["metrics"]["avg_sources_retrieved"] = sum(sources_counts) / len(sources_counts)
        if quality_scores:
            summary["metrics"]["avg_quality_score"] = sum(quality_scores) / len(quality_scores)

        summary["quality_scores"] = quality_scores
        return summary

    def save_report(self, output_path: str) -> None:
        """Save test results to a JSON report file."""
        summary = self._generate_summary(0)  # Time is already in results
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
        }

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to {output_path}")
        self._print_summary(summary)

    def _print_summary(self, summary: dict) -> None:
        """Print a formatted summary to console."""
        if not summary:
            return

        print("\n" + "=" * 70)
        print("REGRESSION TEST SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Successful: {summary['successful_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Total Time: {summary['total_time_seconds']:.2f}s")
        print("\nQUALITY METRICS:")
        metrics = summary.get("metrics", {})
        print(f"  False No-Info Responses: {metrics.get('false_no_info_responses', 0)}")
        print(f"  Label Leakage Instances: {metrics.get('label_leakage_count', 0)}")
        print(f"  Truncated Answers: {metrics.get('truncated_answers', 0)}")
        print(f"  Incomplete Answers: {metrics.get('incomplete_answers', 0)}")
        print(f"  Avg Answer Length: {metrics.get('avg_answer_length', 0):.0f} chars")
        print(f"  Avg Response Time: {metrics.get('avg_response_time', 0):.2f}s")
        print(f"  Avg Sources Retrieved: {metrics.get('avg_sources_retrieved', 0):.1f}")
        print(f"  Avg Quality Score: {metrics.get('avg_quality_score', 0):.1f}/100")
        print("\nPIPELINE ACTIVATION:")
        print(f"  Fallback Used: {metrics.get('used_fallback', 0)} times")
        print(f"  Rescue Used: {metrics.get('used_rescue', 0)} times")
        print(f"  Incomplete Detection: {metrics.get('used_incomplete_detection', 0)} times")
        print("=" * 70)


def load_test_cases(config_path: str) -> list[dict]:
    """Load test cases from a JSON configuration file."""
    path = Path(config_path)
    if not path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)

    with open(path, "r") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and "test_cases" in data:
        return data["test_cases"]
    else:
        print("Error: Configuration file must contain a list of test cases or a 'test_cases' key")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Run regression tests for the DEO RAG system"
    )
    parser.add_argument(
        "--config",
        default="test_cases.json",
        help="Path to test cases configuration file (default: test_cases.json)",
    )
    parser.add_argument(
        "--output",
        default="test_results.json",
        help="Path to save test report (default: test_results.json)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the RAG API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Request timeout in seconds (default: 60)",
    )

    args = parser.parse_args()

    try:
        test_cases = load_test_cases(args.config)
    except Exception as e:
        print(f"Error loading test cases: {e}")
        sys.exit(1)

    tester = RegressionTester(base_url=args.base_url, timeout=args.timeout)
    tester.run_test_suite(test_cases)
    tester.save_report(args.output)


if __name__ == "__main__":
    main()
