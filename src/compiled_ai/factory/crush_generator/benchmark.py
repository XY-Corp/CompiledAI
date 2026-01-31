#!/usr/bin/env python3
"""Standalone benchmark for the Crush workflow generator.

This benchmark tests the generator's ability to create working workflow code
from natural language descriptions.

Metrics collected:
- Success rate
- First-try success rate
- Average iterations needed
- Average time per workflow

Usage:
    python benchmark.py
    python benchmark.py --max-tasks 10 --verbose
    python benchmark.py --model gemini/gemini-2.5-pro
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from generator import CrushGenerator, GenerationResult
except ImportError:
    from .generator import CrushGenerator, GenerationResult


@dataclass
class TaskResult:
    """Result from generating a workflow for a single task."""
    task_id: str
    task_description: str
    success: bool
    iterations: int
    first_try_success: bool
    generation_time_seconds: float
    workflow_path: str | None = None
    activities_path: str | None = None
    error: str | None = None
    metrics: dict = field(default_factory=dict)


@dataclass  
class BenchmarkResult:
    """Aggregate benchmark results."""
    results: list[TaskResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    model: str = ""
    
    @property
    def success_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.success) / len(self.results)
    
    @property
    def first_try_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.first_try_success) / len(self.results)
    
    @property
    def avg_iterations(self) -> float:
        successful = [r for r in self.results if r.success]
        if not successful:
            return 0.0
        return sum(r.iterations for r in successful) / len(successful)
    
    @property
    def avg_time_seconds(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.generation_time_seconds for r in self.results) / len(self.results)
    
    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time
    
    def to_dict(self) -> dict:
        return {
            "summary": {
                "total_tasks": len(self.results),
                "success_rate": self.success_rate,
                "first_try_rate": self.first_try_rate,
                "avg_iterations": self.avg_iterations,
                "avg_time_seconds": self.avg_time_seconds,
                "total_duration_seconds": self.duration_seconds,
                "model": self.model,
            },
            "results": [
                {
                    "task_id": r.task_id,
                    "task_description": r.task_description[:100],
                    "success": r.success,
                    "iterations": r.iterations,
                    "first_try_success": r.first_try_success,
                    "generation_time_seconds": r.generation_time_seconds,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


# Sample benchmark tasks of varying complexity
BENCHMARK_TASKS = [
    # Simple tasks
    {
        "id": "simple_01_email_validation",
        "category": "simple",
        "description": """
Create a workflow that:
1. Takes a list of email addresses as input
2. Validates each email format using regex
3. Returns a dict with 'valid' and 'invalid' lists
""",
    },
    {
        "id": "simple_02_text_stats",
        "category": "simple",
        "description": """
Create a workflow that:
1. Takes a text string as input
2. Counts words, sentences, and characters
3. Returns a dict with the statistics
""",
    },
    {
        "id": "simple_03_list_filter",
        "category": "simple",
        "description": """
Create a workflow that:
1. Takes a list of numbers
2. Filters to keep only positive even numbers
3. Returns the filtered list sorted in ascending order
""",
    },
    
    # Multi-step tasks
    {
        "id": "multi_01_data_pipeline",
        "category": "multi-step",
        "description": """
Create a workflow that:
1. Takes a list of user dicts with 'name', 'age', 'email'
2. Validates that age is positive and email format is valid
3. Filters users who are 18 or older
4. Groups users by first letter of name
5. Returns the grouped data as a dict
""",
    },
    {
        "id": "multi_02_text_processor",
        "category": "multi-step",
        "description": """
Create a workflow that:
1. Takes raw text input
2. Cleans the text (remove extra whitespace, normalize)
3. Extracts all URLs from the text
4. Extracts all email addresses
5. Returns a dict with 'cleaned_text', 'urls', and 'emails'
""",
    },
    {
        "id": "multi_03_json_transformer",
        "category": "multi-step",
        "description": """
Create a workflow that:
1. Takes a nested JSON structure as input
2. Flattens it to a single-level dict with dot notation keys
3. Filters out any null values
4. Sorts keys alphabetically
5. Returns the transformed dict
""",
    },
    
    # Complex tasks
    {
        "id": "complex_01_analytics",
        "category": "complex",
        "description": """
Create a workflow that:
1. Takes a list of sales records with 'product', 'amount', 'date', 'region'
2. Groups sales by region
3. Calculates total and average for each region
4. Finds the top-selling product per region
5. Returns a comprehensive analytics report as a dict
""",
    },
    {
        "id": "complex_02_validation_suite",
        "category": "complex",
        "description": """
Create a workflow that:
1. Takes a configuration dict with various settings
2. Validates each setting against type requirements
3. Checks for required fields
4. Applies default values for missing optional fields
5. Returns validation result with any errors and the final config
""",
    },
]


def run_benchmark(
    tasks: list[dict],
    generator: CrushGenerator,
    output_dir: Path,
    verbose: bool = False,
) -> BenchmarkResult:
    """Run benchmark on all tasks."""
    result = BenchmarkResult()
    result.start_time = time.time()
    result.model = generator._active_model or "unknown"
    
    print(f"\n{'='*60}")
    print(f"Running {len(tasks)} tasks with model: {result.model}")
    print(f"{'='*60}\n")
    
    for i, task in enumerate(tasks):
        task_id = task["id"]
        description = task["description"]
        category = task.get("category", "unknown")
        
        print(f"[{i+1}/{len(tasks)}] {task_id} ({category})")
        
        # Create task output directory
        task_dir = output_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Run generation
        start = time.time()
        try:
            gen_result = generator.generate(
                description,
                output_dir=task_dir,
                verbose=verbose,
            )
            duration = time.time() - start
            
            task_result = TaskResult(
                task_id=task_id,
                task_description=description[:200],
                success=gen_result.success,
                iterations=gen_result.iterations,
                first_try_success=gen_result.metrics.first_try_success if gen_result.metrics else False,
                generation_time_seconds=duration,
                workflow_path=str(gen_result.workflow_path) if gen_result.workflow_path else None,
                activities_path=str(gen_result.activities_path) if gen_result.activities_path else None,
                error=gen_result.errors[-1][:200] if gen_result.errors else None,
                metrics=gen_result.metrics.to_dict() if gen_result.metrics else {},
            )
            
        except Exception as e:
            duration = time.time() - start
            task_result = TaskResult(
                task_id=task_id,
                task_description=description[:200],
                success=False,
                iterations=0,
                first_try_success=False,
                generation_time_seconds=duration,
                error=str(e)[:200],
            )
        
        result.results.append(task_result)
        
        # Print status
        status = "✓" if task_result.success else "✗"
        first_try = " (1st try)" if task_result.first_try_success else f" ({task_result.iterations} iter)"
        print(f"  {status} {duration:.1f}s{first_try}")
        
        if not task_result.success and task_result.error:
            print(f"    Error: {task_result.error[:80]}...")
        
        # Save incremental results
        _save_results(result, output_dir)
    
    result.end_time = time.time()
    return result


def _save_results(result: BenchmarkResult, output_dir: Path) -> None:
    """Save current results to file."""
    results_file = output_dir / "benchmark_results.json"
    with open(results_file, "w") as f:
        json.dump(result.to_dict(), f, indent=2)


def print_summary(result: BenchmarkResult) -> None:
    """Print benchmark summary."""
    print(f"\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}\n")
    
    print(f"  Model: {result.model}")
    print(f"  Total Tasks: {len(result.results)}")
    print(f"  Duration: {result.duration_seconds:.1f}s\n")
    
    # Success metrics
    print(f"  Success Rate: {result.success_rate:.1%}")
    print(f"  First-Try Success: {result.first_try_rate:.1%}")
    print(f"  Avg Iterations: {result.avg_iterations:.2f}")
    print(f"  Avg Time/Task: {result.avg_time_seconds:.1f}s")
    
    # Category breakdown
    categories = {}
    for r in result.results:
        # Extract category from task ID
        cat = r.task_id.split("_")[0] if "_" in r.task_id else "other"
        if cat not in categories:
            categories[cat] = {"total": 0, "success": 0, "first_try": 0}
        categories[cat]["total"] += 1
        if r.success:
            categories[cat]["success"] += 1
        if r.first_try_success:
            categories[cat]["first_try"] += 1
    
    if len(categories) > 1:
        print(f"\n  By Category:")
        for cat, stats in categories.items():
            success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
            print(f"    {cat}: {success_rate:.0%} ({stats['success']}/{stats['total']})")
    
    # Failures
    failures = [r for r in result.results if not r.success]
    if failures:
        print(f"\n  Failures ({len(failures)}):")
        for f in failures[:5]:
            error = f.error[:60] if f.error else "Unknown"
            print(f"    - {f.task_id}: {error}...")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Benchmark Crush workflow generator"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (auto-detect if not specified)",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Maximum tasks to run (default: all)",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=["simple", "multi-step", "complex"],
        default=None,
        help="Categories to run (default: all)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Max fix iterations per task (default: 3)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="benchmark_results",
        help="Output directory for results",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("CRUSH GENERATOR BENCHMARK")
    print("="*60)
    
    # Filter tasks by category
    tasks = BENCHMARK_TASKS
    if args.categories:
        tasks = [t for t in tasks if t.get("category") in args.categories]
    
    if args.max_tasks:
        tasks = tasks[:args.max_tasks]
    
    print(f"\nSelected {len(tasks)} tasks")
    
    if not tasks:
        print("No tasks selected!")
        sys.exit(1)
    
    # Initialize generator
    try:
        generator = CrushGenerator(
            model=args.model,
            max_iterations=args.max_iterations,
            timeout_per_step=180,
            enable_security_validation=False,
        )
        # Force model detection
        generator._get_runner()
        print(f"Using model: {generator._active_model}")
    except RuntimeError as e:
        print(f"Error: {e}")
        print("\nMake sure Crush is installed and API credentials are configured.")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Output: {run_dir}")
    
    # Run benchmark
    result = run_benchmark(
        tasks,
        generator,
        run_dir,
        verbose=args.verbose,
    )
    
    # Save final results
    _save_results(result, run_dir)
    
    # Print summary
    print_summary(result)
    
    print(f"\nResults saved to: {run_dir}/benchmark_results.json")
    
    # Exit code
    sys.exit(0 if result.success_rate >= 0.5 else 1)


if __name__ == "__main__":
    main()
