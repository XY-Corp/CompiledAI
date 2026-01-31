#!/usr/bin/env python3
"""Test script for the Crush-based workflow generator.

This test script provides:
1. Unit tests for CrushRunner and CrushGenerator
2. Integration tests with real models (if available)
3. Sample workflows of varying complexity

Usage:
    # Run all tests
    python test_generator.py
    
    # Run with verbose output
    python test_generator.py -v
    
    # Run only unit tests (no API calls)
    python test_generator.py --unit-only
    
    # Test with specific model
    python test_generator.py --model anthropic/claude-opus-4-5-20251101
"""

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from runner import CrushRunner, CrushOutput
from generator import CrushGenerator, GenerationResult, GenerationMetrics


# Test workflows of increasing complexity
SAMPLE_WORKFLOWS = {
    "simple": {
        "name": "Email Validator",
        "description": """
        Create a workflow that:
        1. Takes a list of email addresses
        2. Validates each email format using regex
        3. Returns a dict with 'valid' and 'invalid' lists
        """,
        "expected_activities": ["validate_email", "categorize_emails"],
    },
    "multi_step": {
        "name": "Data Pipeline",
        "description": """
        Create a workflow that:
        1. Takes raw JSON data as input
        2. Parses and validates the JSON structure
        3. Transforms the data (flatten nested objects)
        4. Filters records based on a condition (e.g., age > 18)
        5. Aggregates results (count, sum, average)
        6. Returns a summary report as a dict
        """,
        "expected_activities": [
            "parse_json",
            "validate_schema",
            "flatten_data",
            "filter_records",
            "aggregate_results",
        ],
    },
    "parallel": {
        "name": "Multi-Source Aggregator",
        "description": """
        Create a workflow that:
        1. Takes a list of data sources (dicts with 'type' and 'data')
        2. Processes each source in parallel based on its type:
           - For 'numbers': calculate statistics
           - For 'text': count words and characters
           - For 'list': get unique items and count
        3. Merges all results into a unified report
        4. Returns the combined analysis
        
        Use a foreach execution pattern for parallel processing.
        """,
        "expected_activities": [
            "process_numbers",
            "process_text",
            "process_list",
            "merge_results",
        ],
    },
    "error_handling": {
        "name": "Resilient Processor",
        "description": """
        Create a workflow that:
        1. Takes a list of items to process
        2. Processes each item with validation
        3. Handles errors gracefully (continues on failure)
        4. Tracks success/failure for each item
        5. Returns results with detailed error info
        
        Each activity should have proper error handling and
        return partial results even if some items fail.
        """,
        "expected_activities": [
            "validate_item",
            "process_item",
            "handle_errors",
            "collect_results",
        ],
    },
}


@dataclass
class TestResult:
    """Result of a test run."""
    name: str
    passed: bool
    message: str
    duration_seconds: float = 0.0
    details: dict = None


class TestSuite:
    """Test suite for the Crush generator."""
    
    def __init__(self, model: str = None, verbose: bool = False):
        self.model = model
        self.verbose = verbose
        self.results: list[TestResult] = []
    
    def log(self, msg: str):
        """Log a message if verbose."""
        if self.verbose:
            print(msg)
    
    def add_result(self, result: TestResult):
        """Add a test result."""
        self.results.append(result)
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"  {status}: {result.name}")
        if not result.passed and result.message:
            print(f"         {result.message[:100]}")
    
    def run_unit_tests(self):
        """Run unit tests that don't require API access."""
        print("\n" + "=" * 60)
        print("Unit Tests (no API required)")
        print("=" * 60)
        
        # Test 1: CrushRunner initialization
        try:
            runner = CrushRunner(model="test/model")
            self.add_result(TestResult(
                name="CrushRunner initialization",
                passed=True,
                message="Runner created successfully",
            ))
        except RuntimeError as e:
            if "not found" in str(e):
                self.add_result(TestResult(
                    name="CrushRunner initialization",
                    passed=False,
                    message="Crush CLI not installed",
                ))
            else:
                raise
        
        # Test 2: GenerationResult serialization
        result = GenerationResult(
            success=True,
            workflow_yaml="test: yaml",
            activities_code="print('test')",
            iterations=2,
            errors=["error1"],
        )
        serialized = result.to_dict()
        self.add_result(TestResult(
            name="GenerationResult serialization",
            passed="workflow_yaml" in serialized and serialized["success"],
            message="Serialization works correctly",
        ))
        
        # Test 3: GenerationMetrics
        from generator import MetricEntry
        metrics = GenerationMetrics()
        metrics.add(MetricEntry(
            stage="planning",
            success=True,
            duration_seconds=1.5,
            model="test/model",
        ))
        metrics_dict = metrics.to_dict()
        self.add_result(TestResult(
            name="GenerationMetrics tracking",
            passed=len(metrics_dict["entries"]) == 1,
            message="Metrics tracked correctly",
        ))
        
        # Test 4: CrushGenerator initialization (validators)
        try:
            generator = CrushGenerator(
                model="test/model",
                max_iterations=3,
            )
            has_validators = generator._validators_available
            self.add_result(TestResult(
                name="CrushGenerator initialization",
                passed=True,
                message=f"Validators available: {has_validators}",
            ))
        except Exception as e:
            self.add_result(TestResult(
                name="CrushGenerator initialization",
                passed=False,
                message=str(e),
            ))
    
    def run_integration_tests(self):
        """Run integration tests that require API access."""
        print("\n" + "=" * 60)
        print("Integration Tests (API required)")
        print("=" * 60)
        
        # Check if model is available
        try:
            generator = CrushGenerator(
                model=self.model,
                max_iterations=3,
                timeout_per_step=120,
            )
        except RuntimeError as e:
            print(f"\n⚠️ Skipping integration tests: {e}")
            return
        
        # Test simple workflow
        self._test_workflow("simple", generator)
        
        # Test multi-step workflow
        self._test_workflow("multi_step", generator)
    
    def _test_workflow(self, workflow_key: str, generator: CrushGenerator):
        """Test a specific workflow."""
        import time
        
        workflow = SAMPLE_WORKFLOWS[workflow_key]
        start_time = time.time()
        
        self.log(f"\nTesting workflow: {workflow['name']}")
        self.log(f"Description: {workflow['description'][:100]}...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generator.generate(
                workflow["description"],
                output_dir=Path(tmpdir),
                verbose=self.verbose,
            )
            
            duration = time.time() - start_time
            
            # Check results
            passed = result.success
            message = ""
            
            if not passed:
                message = f"Failed after {result.iterations} iterations"
                if result.errors:
                    message += f": {result.errors[-1][:80]}"
            else:
                # Check if expected activities are present
                if result.workflow_yaml:
                    for activity in workflow.get("expected_activities", []):
                        if activity not in result.workflow_yaml:
                            self.log(f"  ⚠️ Expected activity not found: {activity}")
            
            self.add_result(TestResult(
                name=f"Workflow: {workflow['name']}",
                passed=passed,
                message=message,
                duration_seconds=duration,
                details={
                    "iterations": result.iterations,
                    "first_try": result.metrics.first_try_success if result.metrics else False,
                },
            ))
    
    def run_all(self, unit_only: bool = False):
        """Run all tests."""
        self.run_unit_tests()
        
        if not unit_only:
            self.run_integration_tests()
        
        # Print summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        print(f"\n  Passed: {passed}/{total}")
        
        if passed == total:
            print("\n  🎉 All tests passed!")
            return 0
        else:
            print("\n  ❌ Some tests failed")
            return 1


def test_runner_basic():
    """Basic test for CrushRunner."""
    print("=" * 60)
    print("Testing CrushRunner (basic)")
    print("=" * 60)
    
    try:
        runner = CrushRunner(model="anthropic/claude-sonnet-4-5-20250929")
        print(f"✅ Runner initialized with model: {runner.model}")
        print(f"   Crush path: {runner._crush_path}")
        print(f"   Timeout: {runner.timeout}s")
        return True
    except RuntimeError as e:
        print(f"❌ Runner initialization failed: {e}")
        return False


def test_generator_with_model(model: str, verbose: bool = True):
    """Test the full CrushGenerator pipeline with a specific model."""
    print("\n" + "=" * 60)
    print(f"Testing CrushGenerator with {model}")
    print("=" * 60)
    
    generator = CrushGenerator(
        model=model,
        max_iterations=3,
        timeout_per_step=120,
    )
    
    task = SAMPLE_WORKFLOWS["simple"]["description"]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        result = generator.generate(
            task,
            output_dir=Path(tmpdir),
            verbose=verbose,
        )
        
        print("\n" + "-" * 40)
        print("Generation Result:")
        print(f"  Success: {result.success}")
        print(f"  Iterations: {result.iterations}")
        print(f"  Time: {result.total_time_seconds:.1f}s")
        
        if result.metrics:
            print(f"  First-try success: {result.metrics.first_try_success}")
        
        if result.errors:
            print(f"  Last error: {result.errors[-1][:80]}...")
        
        if result.workflow_yaml:
            print(f"\n📋 Workflow YAML ({len(result.workflow_yaml)} chars)")
            if verbose:
                print(result.workflow_yaml[:500])
        
        if result.activities_code:
            print(f"\n🐍 Activities ({len(result.activities_code)} chars)")
            if verbose:
                print(result.activities_code[:500])
        
        # Save metrics if successful
        if result.metrics:
            metrics_path = Path(tmpdir) / "metrics.json"
            metrics_path.write_text(json.dumps(result.metrics.to_dict(), indent=2))
            print(f"\n📊 Metrics saved to: {metrics_path}")
        
        return result.success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test the Crush workflow generator")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--unit-only", action="store_true", 
                        help="Run only unit tests (no API calls)")
    parser.add_argument("-m", "--model", help="Model to use for integration tests",
                        default=None)
    parser.add_argument("--basic", action="store_true",
                        help="Run basic tests only (original test mode)")
    
    args = parser.parse_args()
    
    print("🧪 Crush Generator Test Suite\n")
    
    if args.basic:
        # Original test mode
        runner_ok = test_runner_basic()
        if runner_ok and args.model:
            generator_ok = test_generator_with_model(args.model, args.verbose)
        else:
            generator_ok = False
        
        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  Runner: {'✅ PASS' if runner_ok else '❌ FAIL'}")
        print(f"  Generator: {'✅ PASS' if generator_ok else '❌ FAIL or SKIPPED'}")
        return 0 if runner_ok else 1
    
    # Run test suite
    suite = TestSuite(model=args.model, verbose=args.verbose)
    return suite.run_all(unit_only=args.unit_only)


if __name__ == "__main__":
    sys.exit(main())
