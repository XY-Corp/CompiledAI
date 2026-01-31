#!/usr/bin/env python3
"""Benchmark the Crush-based workflow generator using BFCL-derived tasks.

This benchmark evaluates the Crush generator's ability to:
1. Generate valid workflow YAML from natural language
2. Generate working Python activity implementations
3. Pass validation and testing

Metrics collected:
- Success rate (how often does it generate working code?)
- Iterations needed (first-try vs needing fixes)
- Time per workflow
- Token usage (via Crush CLI metrics when available)

Usage:
    python scripts/run_crush_benchmark.py
    python scripts/run_crush_benchmark.py --max-tasks 10 --verbose
    python scripts/run_crush_benchmark.py --categories simple multiple
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compiled_ai.datasets import BFCLConverter
from compiled_ai.datasets.bfcl_tools import build_tools_from_functions
from compiled_ai.factory.crush_generator import CrushGenerator, GenerationResult


console = Console()


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
                    "success": r.success,
                    "iterations": r.iterations,
                    "first_try_success": r.first_try_success,
                    "generation_time_seconds": r.generation_time_seconds,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


def create_workflow_task(bfcl_instance: Any) -> dict:
    """Convert a BFCL instance into a workflow generation task.
    
    BFCL instances have function definitions. We create a task
    that asks the generator to build a workflow using those functions.
    """
    # Parse the BFCL input
    try:
        bfcl_data = json.loads(bfcl_instance.input)
        question = bfcl_data.get("question", "")
        functions = bfcl_data.get("function", [])
    except json.JSONDecodeError:
        return None
    
    # Build a natural language task description
    if isinstance(question, list) and question:
        # BFCL format: [[{"role": "user", "content": "..."}]]
        if isinstance(question[0], list) and question[0]:
            user_query = question[0][0].get("content", "") if isinstance(question[0][0], dict) else str(question[0][0])
        elif isinstance(question[0], dict):
            user_query = question[0].get("content", str(question))
        else:
            user_query = str(question)
    else:
        user_query = str(question)
    
    # Extract function signatures for the task
    func_descriptions = []
    for func in functions[:3]:  # Limit to first 3 functions
        name = func.get("name", "unknown")
        desc = func.get("description", "")
        params = func.get("parameters", {}).get("properties", {})
        param_list = ", ".join(params.keys())
        func_descriptions.append(f"- {name}({param_list}): {desc[:100]}")
    
    task_description = f"""Create a workflow that answers: "{user_query}"

Available functions to implement:
{chr(10).join(func_descriptions)}

Requirements:
1. Create proper workflow YAML with activity definitions
2. Implement each activity as a Python function
3. Include input validation and error handling
4. Add test cases that verify the implementation works
"""
    
    return {
        "task_id": bfcl_instance.id,
        "description": task_description,
        "original_question": user_query,
        "functions": functions,
    }


def load_bfcl_tasks(
    dataset_path: Path,
    categories: list[str] | None = None,
    max_per_category: int = 5,
) -> list[dict]:
    """Load BFCL tasks and convert to workflow generation tasks."""
    from compiled_ai.runner.loader import BFCLAdapter
    
    converter = BFCLConverter()
    tasks = []
    
    # Default to simpler categories for workflow generation
    if categories is None:
        categories = ["simple", "multiple"]
    
    for category in categories:
        cat_info = BFCLAdapter.CATEGORIES.get(category)
        if not cat_info:
            console.print(f"[yellow]Unknown category: {category}[/yellow]")
            continue
        
        filename = cat_info.get("file", f"BFCL_v3_{category}.json")
        file_path = dataset_path / filename
        
        if not file_path.exists():
            console.print(f"[yellow]File not found: {file_path}[/yellow]")
            continue
        
        try:
            instances = converter.load_file(str(file_path))
            console.print(f"[dim]Loaded {len(instances)} instances from {category}[/dim]")
            
            # Convert to workflow tasks
            for inst in instances[:max_per_category]:
                task = create_workflow_task(inst)
                if task:
                    task["category"] = category
                    tasks.append(task)
                    
        except Exception as e:
            console.print(f"[red]Error loading {category}: {e}[/red]")
    
    return tasks


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
    
    console.print(f"\n[bold]Running {len(tasks)} tasks...[/bold]\n")
    
    for i, task in enumerate(tasks):
        task_id = task["task_id"]
        description = task["description"]
        
        console.print(f"[{i+1}/{len(tasks)}] {task_id}")
        
        # Create task output directory
        task_dir = output_dir / task_id.replace("/", "_")
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
                error=gen_result.errors[-1] if gen_result.errors else None,
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
                error=str(e),
            )
        
        result.results.append(task_result)
        
        # Print status
        status = "[green]✓[/green]" if task_result.success else "[red]✗[/red]"
        first_try = " (1st try)" if task_result.first_try_success else f" ({task_result.iterations} iter)"
        console.print(f"  {status} {duration:.1f}s{first_try}")
        
        # Save incremental results
        _save_incremental_results(result, output_dir)
    
    result.end_time = time.time()
    return result


def _save_incremental_results(result: BenchmarkResult, output_dir: Path) -> None:
    """Save current results to file."""
    results_file = output_dir / "benchmark_results.json"
    with open(results_file, "w") as f:
        json.dump(result.to_dict(), f, indent=2)


def print_results_table(result: BenchmarkResult) -> None:
    """Print results summary table."""
    table = Table(title="Benchmark Results", box=box.ROUNDED)
    table.add_column("Task ID", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Iterations", justify="right")
    table.add_column("Time (s)", justify="right")
    table.add_column("First Try", justify="center")
    
    for r in result.results:
        status = "[green]✓[/green]" if r.success else "[red]✗[/red]"
        first_try = "[green]✓[/green]" if r.first_try_success else "[dim]-[/dim]"
        table.add_row(
            r.task_id[:30],
            status,
            str(r.iterations),
            f"{r.generation_time_seconds:.1f}",
            first_try,
        )
    
    console.print(table)


def print_summary(result: BenchmarkResult) -> None:
    """Print benchmark summary."""
    console.print("\n[bold]═══ Benchmark Summary ═══[/bold]\n")
    
    console.print(f"  Model: [cyan]{result.model}[/cyan]")
    console.print(f"  Total Tasks: [cyan]{len(result.results)}[/cyan]")
    console.print(f"  Duration: [cyan]{result.duration_seconds:.1f}s[/cyan]\n")
    
    # Success metrics
    success_style = "green" if result.success_rate >= 0.8 else "yellow" if result.success_rate >= 0.5 else "red"
    console.print(f"  Success Rate: [{success_style}]{result.success_rate:.1%}[/{success_style}]")
    
    first_try_style = "green" if result.first_try_rate >= 0.5 else "yellow" if result.first_try_rate >= 0.3 else "red"
    console.print(f"  First-Try Success: [{first_try_style}]{result.first_try_rate:.1%}[/{first_try_style}]")
    
    console.print(f"  Avg Iterations: [cyan]{result.avg_iterations:.2f}[/cyan]")
    console.print(f"  Avg Time/Task: [cyan]{result.avg_time_seconds:.1f}s[/cyan]")
    
    # Failure analysis
    failures = [r for r in result.results if not r.success]
    if failures:
        console.print(f"\n[yellow]Failures ({len(failures)}):[/yellow]")
        for f in failures[:3]:
            error_preview = f.error[:80] if f.error else "Unknown"
            console.print(f"  - {f.task_id}: {error_preview}...")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Benchmark Crush workflow generator with BFCL tasks"
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default="datasets/bfcl_v4",
        help="Path to BFCL dataset",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=["simple"],
        help="BFCL categories to use (default: simple)",
    )
    parser.add_argument(
        "--max-per-category",
        type=int,
        default=5,
        help="Max tasks per category (default: 5)",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Maximum total tasks to run",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (auto-detect if not specified)",
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
        default="results/crush_benchmark",
        help="Output directory for results",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    console.print("[bold blue]Crush Generator Benchmark[/bold blue]\n")
    
    # Check dataset
    dataset_path = Path(args.dataset_path)
    if not dataset_path.exists():
        console.print(f"[red]Dataset not found: {dataset_path}[/red]")
        console.print("Run: python scripts/download_bfcl.py")
        sys.exit(1)
    
    # Load tasks
    console.print("[yellow]Loading BFCL tasks...[/yellow]")
    tasks = load_bfcl_tasks(
        dataset_path,
        categories=args.categories,
        max_per_category=args.max_per_category,
    )
    
    if args.max_tasks:
        tasks = tasks[:args.max_tasks]
    
    console.print(f"Loaded [cyan]{len(tasks)}[/cyan] tasks\n")
    
    if not tasks:
        console.print("[red]No tasks loaded. Check dataset and categories.[/red]")
        sys.exit(1)
    
    # Initialize generator
    try:
        generator = CrushGenerator(
            model=args.model,
            max_iterations=args.max_iterations,
            timeout_per_step=180,
            enable_security_validation=False,  # Skip for speed
        )
        console.print(f"[green]Generator initialized[/green]")
    except RuntimeError as e:
        console.print(f"[red]Failed to initialize generator: {e}[/red]")
        console.print("\nMake sure Crush is installed and API credentials are configured:")
        console.print("  - AWS Bedrock: Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        console.print("  - Gemini: Set GOOGLE_API_KEY")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(f"Output directory: [cyan]{run_dir}[/cyan]\n")
    
    # Run benchmark
    result = run_benchmark(
        tasks,
        generator,
        run_dir,
        verbose=args.verbose,
    )
    
    # Print results
    print_results_table(result)
    print_summary(result)
    
    # Save final results
    results_file = run_dir / "benchmark_results.json"
    with open(results_file, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    
    console.print(f"\n[dim]Results saved to: {results_file}[/dim]")
    
    # Exit code based on success rate
    sys.exit(0 if result.success_rate >= 0.5 else 1)


if __name__ == "__main__":
    main()
