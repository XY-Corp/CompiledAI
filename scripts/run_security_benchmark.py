#!/usr/bin/env python3
"""Security Benchmark Runner for CompiledAI.

Tests the security validation pipeline (PromptInjection, PII, Canary, CodeShield)
against the security benchmark dataset.

Usage:
    python scripts/run_security_benchmark.py
    python scripts/run_security_benchmark.py --max-instances 10
    python scripts/run_security_benchmark.py --category input_injection
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path for imports when running from scripts/
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single test case."""

    test_id: str
    test_name: str
    expected: bool  # Expected to be flagged/blocked
    actual: bool  # Actually flagged/blocked
    correct: bool  # Expected == Actual
    latency_ms: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CategoryResult:
    """Aggregated results for a test category."""

    category: str
    total: int
    true_positive: int  # Correctly flagged threats
    true_negative: int  # Correctly allowed clean
    false_positive: int  # Incorrectly flagged clean
    false_negative: int  # Incorrectly allowed threats
    avg_latency_ms: float
    results: list[TestResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        """Overall accuracy."""
        if self.total == 0:
            return 0.0
        return (self.true_positive + self.true_negative) / self.total

    @property
    def precision(self) -> float:
        """Precision (TP / (TP + FP))."""
        total_flagged = self.true_positive + self.false_positive
        if total_flagged == 0:
            return 1.0
        return self.true_positive / total_flagged

    @property
    def recall(self) -> float:
        """Recall (TP / (TP + FN))."""
        total_threats = self.true_positive + self.false_negative
        if total_threats == 0:
            return 1.0
        return self.true_positive / total_threats


def load_dataset(category: str) -> dict[str, Any]:
    """Load a security benchmark dataset file.

    Handles both flat structure (category.json) and subfolder structure (gate/category.json).
    """
    base_path = PROJECT_ROOT / "datasets/security_benchmark/tasks"

    # Map category to actual file paths
    category_paths = {
        "input_injection": base_path / "input_gate" / "input_injection.json",
        "input_pii": base_path / "input_gate" / "input_pii.json",
        "output_leakage": base_path / "output_gate" / "output_leakage.json",
        "code_safety": base_path / "code_gate" / "code_safety.json",
    }

    # Try mapped path first, then flat path
    dataset_path = category_paths.get(category, base_path / f"{category}.json")
    if not dataset_path.exists():
        # Try flat path as fallback
        dataset_path = base_path / f"{category}.json"
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    with open(dataset_path) as f:
        return json.load(f)


def run_injection_tests(
    instances: list[dict[str, Any]],
    max_instances: int | None = None,
) -> CategoryResult:
    """Run prompt injection tests."""
    from compiled_ai.validation import PromptInjectionValidator

    validator = PromptInjectionValidator()
    results: list[TestResult] = []
    latencies: list[float] = []

    tp, tn, fp, fn = 0, 0, 0, 0

    test_instances = instances[:max_instances] if max_instances else instances

    for instance in test_instances:
        test_id = instance["id"]
        test_name = instance["name"]
        user_request = instance["input"]["user_request"]
        expected_blocked = instance["expected_output"]["blocked"]

        start = time.perf_counter()
        result = validator.validate(user_request)
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)

        actual_blocked = result.is_threat
        correct = actual_blocked == expected_blocked

        # Update confusion matrix
        if expected_blocked and actual_blocked:
            tp += 1
        elif not expected_blocked and not actual_blocked:
            tn += 1
        elif not expected_blocked and actual_blocked:
            fp += 1
        else:
            fn += 1

        results.append(
            TestResult(
                test_id=test_id,
                test_name=test_name,
                expected=expected_blocked,
                actual=actual_blocked,
                correct=correct,
                latency_ms=latency_ms,
                details={
                    "injection_score": result.details.get("injection_score", 0),
                    "label": result.details.get("label", ""),
                },
            )
        )

        status = "[OK]" if correct else "[FAIL]"
        logger.info(f"  {status} {test_id}: {test_name}")

    return CategoryResult(
        category="input_injection",
        total=len(results),
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
        results=results,
    )


def run_pii_tests(
    instances: list[dict[str, Any]],
    max_instances: int | None = None,
) -> CategoryResult:
    """Run PII detection tests."""
    from compiled_ai.validation import PIIScanner

    scanner = PIIScanner()
    results: list[TestResult] = []
    latencies: list[float] = []

    tp, tn, fp, fn = 0, 0, 0, 0

    test_instances = instances[:max_instances] if max_instances else instances

    for instance in test_instances:
        test_id = instance["id"]
        test_name = instance["name"]
        user_request = instance["input"]["user_request"]
        expected_pii = instance["expected_output"]["pii_detected"]

        start = time.perf_counter()
        result = scanner.validate(user_request)
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)

        actual_pii = result.details.get("has_pii", False)
        correct = actual_pii == expected_pii

        # Update confusion matrix
        if expected_pii and actual_pii:
            tp += 1
        elif not expected_pii and not actual_pii:
            tn += 1
        elif not expected_pii and actual_pii:
            fp += 1
        else:
            fn += 1

        results.append(
            TestResult(
                test_id=test_id,
                test_name=test_name,
                expected=expected_pii,
                actual=actual_pii,
                correct=correct,
                latency_ms=latency_ms,
                details={
                    "risk_score": result.details.get("risk_score", 0),
                    "sanitized_length": result.details.get("sanitized_length", 0),
                },
            )
        )

        status = "[OK]" if correct else "[FAIL]"
        logger.info(f"  {status} {test_id}: {test_name}")

    return CategoryResult(
        category="input_pii",
        total=len(results),
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
        results=results,
    )


def run_leakage_tests(
    instances: list[dict[str, Any]],
    max_instances: int | None = None,
) -> CategoryResult:
    """Run canary leakage tests.

    Note: This simulates leakage detection. In real usage, the canary would be
    in the system prompt and we'd check LLM output. Here we test if the attack
    prompts would trigger leakage (by checking if they contain patterns that
    would extract the canary).
    """
    from compiled_ai.validation import CanaryManager

    canary_manager = CanaryManager()
    results: list[TestResult] = []
    latencies: list[float] = []

    tp, tn, fp, fn = 0, 0, 0, 0

    test_instances = instances[:max_instances] if max_instances else instances

    # For leakage tests, we simulate:
    # 1. Inject canary into a mock system prompt
    # 2. Create a mock "leaked" response for attack cases
    # 3. Check if canary detection works

    mock_system_prompt = "You are a helpful assistant for CompiledAI."

    for i, instance in enumerate(test_instances):
        test_id = instance["id"]
        test_name = instance["name"]
        user_request = instance["input"]["user_request"]
        # Dataset uses "blocked" field - if blocked, no leak expected
        expected_blocked = instance["expected_output"].get("blocked", False)
        expected_no_leak = expected_blocked  # blocked means no leak
        attack_type = instance.get("attack_type", "unknown")

        session_id = f"test_session_{i}"

        start = time.perf_counter()

        # Inject canary
        prompt_with_canary = canary_manager.inject_into_prompt(
            mock_system_prompt, session_id
        )
        canary_token = canary_manager.get_token(session_id)

        # Simulate LLM response
        # For attack prompts, simulate that some percentage would leak
        # For negative tests (legitimate requests), no leakage
        is_attack = "extraction" in attack_type or "leak" in test_name.lower()

        if is_attack and "negative" not in test_name.lower():
            # Simulate leaked response (include canary)
            mock_response = f"Here are the instructions: {prompt_with_canary}"
        else:
            # Simulate clean response
            mock_response = "I'll help you create that workflow."

        # Check for leakage
        leakage_result = canary_manager.check_leakage(mock_response, session_id)

        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)

        # For this benchmark, we're testing if canary detection WORKS
        # Expected: no leak in output -> canary_leaked=false -> leakage_result.leaked should match
        actual_leaked = leakage_result.leaked
        actual_no_leak = not actual_leaked

        # The test passes if we correctly detect the leakage state
        correct = actual_leaked == (not expected_no_leak)

        # Confusion matrix: "positive" = correctly detected a leak
        if not expected_no_leak and actual_leaked:
            tp += 1  # Correctly detected leak
        elif expected_no_leak and not actual_leaked:
            tn += 1  # Correctly no false alarm
        elif expected_no_leak and actual_leaked:
            fp += 1  # False alarm
        else:
            fn += 1  # Missed leak

        results.append(
            TestResult(
                test_id=test_id,
                test_name=test_name,
                expected=not expected_no_leak,  # Expected leak
                actual=actual_leaked,
                correct=correct,
                latency_ms=latency_ms,
                details={
                    "attack_type": attack_type,
                    "canary_token": canary_token[:20] + "..." if canary_token else None,
                    "match_position": leakage_result.match_position,
                },
            )
        )

        status = "[OK]" if correct else "[FAIL]"
        logger.info(f"  {status} {test_id}: {test_name}")

    return CategoryResult(
        category="output_leakage",
        total=len(results),
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
        results=results,
    )


def run_code_tests(
    instances: list[dict[str, Any]],
    max_instances: int | None = None,
) -> CategoryResult:
    """Run code safety tests on workflow files.
    
    Tests the enhanced CodeShieldValidator (Bandit + detect-secrets + Semgrep + CodeShield)
    on actual workflow files referenced in the dataset.
    """
    from compiled_ai.validation import CodeShieldValidator

    validator = CodeShieldValidator(severity_threshold="low")
    results: list[TestResult] = []
    latencies: list[float] = []

    tp, tn, fp, fn = 0, 0, 0, 0

    test_instances = instances[:max_instances] if max_instances else instances

    for instance in test_instances:
        test_id = instance["id"]
        test_name = instance["name"]
        file_path = instance["input"]["file_path"]
        expected_unsafe = instance["expected_output"]["unsafe_code_detected"]

        try:
            # Read code from workflow file
            full_path = PROJECT_ROOT / file_path
            if not full_path.exists():
                logger.error(f"File not found: {full_path}")
                continue
                
            code = full_path.read_text()

            start = time.perf_counter()
            result = validator.validate(code)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

            actual_unsafe = not result.success  # success=False means issues found
            correct = actual_unsafe == expected_unsafe

            # Update confusion matrix
            if expected_unsafe and actual_unsafe:
                tp += 1  # Correctly detected vulnerable code
            elif not expected_unsafe and not actual_unsafe:
                tn += 1  # Correctly identified as safe
            elif not expected_unsafe and actual_unsafe:
                fp += 1  # False positive
            else:
                fn += 1  # Missed vulnerability

            results.append(
                TestResult(
                    test_id=test_id,
                    test_name=test_name,
                    expected=expected_unsafe,
                    actual=actual_unsafe,
                    correct=correct,
                    latency_ms=latency_ms,
                    details={
                        "file": str(file_path),
                        "total_issues": result.details.get("total_issues", 0),
                        "severity_counts": result.details.get("severity_counts", {}),
                        "tools_with_findings": result.details.get("tools_with_findings", []),
                        "expected_cwe": instance["expected_output"].get("cwe_id"),
                    },
                )
            )

            status = "[OK]" if correct else "[FAIL]"
            logger.info(f"  {status} {test_id}: {test_name}")

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            continue

    return CategoryResult(
        category="code_safety",
        total=len(results),
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
        results=results,
    )


def print_results(category_results: dict[str, CategoryResult]) -> None:
    """Print formatted benchmark results."""
    print("\n" + "=" * 70)
    print("SECURITY BENCHMARK RESULTS")
    print("=" * 70)

    total_correct = 0
    total_tests = 0

    for category, result in category_results.items():
        total_correct += result.true_positive + result.true_negative
        total_tests += result.total

        # Format latency - use μs for very small values, ms otherwise
        if result.avg_latency_ms < 1.0:
            latency_str = f"{result.avg_latency_ms * 1000:.1f}μs avg"
        else:
            latency_str = f"{result.avg_latency_ms:.1f}ms avg"

        print(f"\n{category.upper()}")
        print("-" * 40)
        print(f"  Total:     {result.total}")
        print(f"  TP:        {result.true_positive}")
        print(f"  TN:        {result.true_negative}")
        print(f"  FP:        {result.false_positive}")
        print(f"  FN:        {result.false_negative}")
        print(f"  Accuracy:  {result.accuracy:.1%}")
        print(f"  Precision: {result.precision:.1%}")
        print(f"  Recall:    {result.recall:.1%}")
        print(f"  Latency:   {latency_str}")

    overall_accuracy = total_correct / total_tests if total_tests > 0 else 0
    print("\n" + "=" * 70)
    print(f"OVERALL SECURITY PASS RATE: {overall_accuracy:.1%}")
    print(f"Total Tests: {total_tests}")
    print("=" * 70 + "\n")


def save_results(
    category_results: dict[str, CategoryResult],
    output_dir: Path = PROJECT_ROOT / "results",
) -> Path:
    """Save benchmark results to JSON."""
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"security_benchmark_{timestamp}.json"

    results_dict = {
        "benchmark": "security_benchmark",
        "timestamp": datetime.now().isoformat(),
        "results": {},
        "aggregate": {},
    }

    total_tp = total_tn = total_fp = total_fn = 0

    for category, result in category_results.items():
        total_tp += result.true_positive
        total_tn += result.true_negative
        total_fp += result.false_positive
        total_fn += result.false_negative

        results_dict["results"][category] = {
            "total": result.total,
            "true_positive": result.true_positive,
            "true_negative": result.true_negative,
            "false_positive": result.false_positive,
            "false_negative": result.false_negative,
            "accuracy": result.accuracy,
            "precision": result.precision,
            "recall": result.recall,
            "avg_latency_ms": result.avg_latency_ms,
            "test_results": [
                {
                    "id": r.test_id,
                    "name": r.test_name,
                    "expected": r.expected,
                    "actual": r.actual,
                    "correct": r.correct,
                    "latency_ms": r.latency_ms,
                    "details": r.details,
                }
                for r in result.results
            ],
        }

    total = total_tp + total_tn + total_fp + total_fn
    results_dict["aggregate"] = {
        "total_tests": total,
        "total_correct": total_tp + total_tn,
        "security_pass_rate": (total_tp + total_tn) / total if total > 0 else 0,
        "overall_precision": total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1,
        "overall_recall": total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1,
    }

    with open(output_file, "w") as f:
        json.dump(results_dict, f, indent=2)

    logger.info(f"Results saved to {output_file}")
    return output_file


def main() -> int:
    """Run the security benchmark."""
    parser = argparse.ArgumentParser(description="Run CompiledAI Security Benchmark")
    parser.add_argument(
        "--max-instances",
        type=int,
        default=None,
        help="Maximum instances per category (default: all)",
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=["input_injection", "input_pii", "output_leakage", "code_safety"],
        default=None,
        help="Run only specific category",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Directory for output files",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 70)
    print("CompiledAI Security Benchmark")
    print("=" * 70)

    category_results: dict[str, CategoryResult] = {}

    # Run standard dataset-based benchmark
    categories = (
        [args.category]
        if args.category
        else ["input_injection", "input_pii", "output_leakage", "code_safety"]
    )

    for category in categories:
        print(f"\nLoading {category} dataset...")
        try:
            dataset = load_dataset(category)
            instances = dataset.get("instances", [])
            print(f"  Found {len(instances)} test instances")

            print(f"\nRunning {category} tests...")

            if category == "input_injection":
                result = run_injection_tests(instances, args.max_instances)
            elif category == "input_pii":
                result = run_pii_tests(instances, args.max_instances)
            elif category == "output_leakage":
                result = run_leakage_tests(instances, args.max_instances)
            elif category == "code_safety":
                result = run_code_tests(instances, args.max_instances)
            else:
                logger.warning(f"Unknown category: {category}")
                continue

            category_results[category] = result

        except FileNotFoundError as e:
            logger.error(f"Dataset not found: {e}")
            continue
        except ImportError as e:
            logger.error(f"Missing dependency for {category}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error running {category}: {e}")
            continue

    if not category_results:
        logger.error("No tests completed successfully")
        return 1

    # Print and save results
    print_results(category_results)
    # If output_dir is relative, make it relative to project root
    output_path = Path(args.output_dir)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    save_results(category_results, output_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
