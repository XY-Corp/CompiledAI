#!/usr/bin/env python3
"""Run the XY_Benchmark dataset with the Direct LLM baseline.

Usage:
    python scripts/run_xy_benchmark.py --provider anthropic
    python scripts/run_xy_benchmark.py --provider gemini --max-instances 2
    python scripts/run_xy_benchmark.py --provider anthropic --task classification_01
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compiled_ai.runner import BenchmarkConfig, BenchmarkRunner, DatasetLoader


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run XY_Benchmark with Direct LLM baseline"
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "gemini", "openai"],
        default="anthropic",
        help="LLM provider to use (default: anthropic)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (default: provider's default)",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Run specific task ID only",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter by category (document_processing, data_transformation, decision_logic, function_calling)",
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        default=None,
        help="Filter by difficulty (simple, medium, complex)",
    )
    parser.add_argument(
        "--max-instances",
        type=int,
        default=None,
        help="Maximum instances per task",
    )
    parser.add_argument(
        "--enable-cache",
        action="store_true",
        help="Enable response caching",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Output directory for results (default: results)",
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="List available tasks and exit",
    )
    return parser.parse_args()


def list_tasks(console: Console) -> None:
    """List all available tasks in XY_Benchmark."""
    loader = DatasetLoader("datasets")
    dataset = loader.load("xy_benchmark")

    table = Table(title="XY_Benchmark Tasks")
    table.add_column("Task ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Category", style="yellow")
    table.add_column("Difficulty", style="magenta")
    table.add_column("Instances", justify="right")

    for task in dataset.tasks:
        table.add_row(
            task.task_id,
            task.name,
            task.category.value,
            task.difficulty.value,
            str(len(task.instances)),
        )

    console.print(table)
    console.print(f"\nTotal: {len(dataset.tasks)} tasks, {sum(len(t.instances) for t in dataset.tasks)} instances")


def run_benchmark(args: argparse.Namespace, console: Console) -> None:
    """Run the benchmark with given arguments."""
    console.print(f"\n[bold blue]XY_Benchmark Runner[/bold blue]")
    console.print(f"Provider: [cyan]{args.provider}[/cyan]")
    if args.model:
        console.print(f"Model: [cyan]{args.model}[/cyan]")
    console.print()

    # Build config
    config = BenchmarkConfig(
        dataset_name="xy_benchmark",
        baseline_name="direct_llm",
        task_ids=[args.task] if args.task else None,
        categories=[args.category] if args.category else None,
        difficulties=[args.difficulty] if args.difficulty else None,
        max_instances=args.max_instances,
        output_dir=Path(args.output_dir),
    )

    # Run benchmark
    runner = BenchmarkRunner(datasets_dir="datasets")

    console.print("[yellow]Running benchmark...[/yellow]\n")

    result = runner.run(
        config,
        provider=args.provider,
        model=args.model,
        enable_cache=args.enable_cache,
    )

    # Display results
    console.print(f"\n[bold green]Results[/bold green]")
    console.print(f"Duration: [cyan]{result.duration_seconds:.2f}s[/cyan]")
    console.print(f"Overall Success Rate: [cyan]{result.overall_success_rate:.1%}[/cyan]")
    console.print()

    # Task-level results table
    table = Table(title="Task Results")
    table.add_column("Task ID", style="cyan")
    table.add_column("Success Rate", justify="right")
    table.add_column("Avg Latency (ms)", justify="right")
    table.add_column("Instances", justify="right")

    for tr in result.task_results:
        success_style = "green" if tr.success_rate >= 0.8 else "yellow" if tr.success_rate >= 0.5 else "red"
        table.add_row(
            tr.task.task_id,
            f"[{success_style}]{tr.success_rate:.1%}[/{success_style}]",
            f"{tr.avg_latency_ms:.0f}",
            str(len(tr.results)),
        )

    console.print(table)

    # Show sample outputs
    console.print("\n[bold]Sample Outputs:[/bold]")
    for tr in result.task_results[:3]:  # Show first 3 tasks
        if tr.results:
            first_result = tr.results[0]
            console.print(f"\n[cyan]{tr.task.task_id}[/cyan]:")
            console.print(f"  Status: {'[green]Success[/green]' if first_result.success else '[red]Failed[/red]'}")
            if first_result.success:
                output_preview = first_result.output[:200] + "..." if len(first_result.output) > 200 else first_result.output
                console.print(f"  Output: {output_preview}")
            elif first_result.error:
                console.print(f"  Error: [red]{first_result.error}[/red]")

    # Save location
    console.print(f"\n[dim]Results saved to: {args.output_dir}/[/dim]")


def main() -> None:
    """Main entry point."""
    console = Console()
    args = parse_args()

    if args.list_tasks:
        list_tasks(console)
        return

    try:
        run_benchmark(args, console)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise


if __name__ == "__main__":
    main()
