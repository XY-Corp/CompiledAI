#!/usr/bin/env python3
"""Run the BFCL v4 dataset with the Direct LLM baseline.

Berkeley Function Calling Leaderboard evaluates function calling accuracy
across multiple categories: simple, multiple, parallel, and more.

Usage:
    python scripts/run_bfcl_benchmark.py --provider anthropic
    python scripts/run_bfcl_benchmark.py --provider gemini --categories simple multiple
    python scripts/run_bfcl_benchmark.py --provider anthropic --max-per-category 10
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compiled_ai.runner import BenchmarkConfig, BenchmarkRunner, DatasetLoader
from compiled_ai.runner.loader import BFCLAdapter


# Available BFCL categories
BFCL_CATEGORIES = list(BFCLAdapter.CATEGORIES.keys())


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run BFCL v4 with Direct LLM baseline"
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
        "--categories",
        nargs="+",
        choices=BFCL_CATEGORIES,
        default=None,
        help=f"Categories to run (default: all). Choices: {', '.join(BFCL_CATEGORIES)}",
    )
    parser.add_argument(
        "--max-per-category",
        type=int,
        default=None,
        help="Maximum instances per category",
    )
    parser.add_argument(
        "--max-instances",
        type=int,
        default=None,
        help="Maximum total instances (applied per task)",
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
        "--dataset-path",
        type=str,
        default="datasets/bfcl_v4",
        help="Path to BFCL dataset (default: datasets/bfcl_v4)",
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List available categories and exit",
    )
    return parser.parse_args()


def list_categories(console: Console) -> None:
    """List all available BFCL categories."""
    table = Table(title="BFCL v4 Categories")
    table.add_column("Category", style="cyan")
    table.add_column("Difficulty", style="magenta")
    table.add_column("Description")

    category_descriptions = {
        "simple": "Single function call",
        "multiple": "Choose from multiple functions",
        "parallel": "Multiple parallel function calls",
        "parallel_multiple": "Parallel calls + multiple function choice",
        "irrelevance": "Detect when no function applies",
        "java": "Java function signatures",
        "javascript": "JavaScript function signatures",
        "rest": "REST API function calls",
        "sql": "SQL database function calls",
    }

    for cat, config in BFCLAdapter.CATEGORIES.items():
        table.add_row(
            cat,
            config["difficulty"],
            category_descriptions.get(cat, "Function calling task"),
        )

    console.print(table)


def run_benchmark(args: argparse.Namespace, console: Console) -> None:
    """Run the benchmark with given arguments."""
    console.print("\n[bold blue]BFCL v4 Benchmark Runner[/bold blue]")
    console.print(f"Provider: [cyan]{args.provider}[/cyan]")
    if args.model:
        console.print(f"Model: [cyan]{args.model}[/cyan]")
    if args.categories:
        console.print(f"Categories: [cyan]{', '.join(args.categories)}[/cyan]")
    console.print()

    # Check if dataset exists
    dataset_path = Path(args.dataset_path)
    if not dataset_path.exists():
        console.print(f"[red]Error: Dataset not found at {dataset_path}[/red]")
        console.print("\nTo download BFCL v4, run:")
        console.print("[cyan]  python scripts/download_bfcl.py[/cyan]")
        sys.exit(1)

    # Load dataset with adapter options
    loader = DatasetLoader("datasets")
    console.print("[yellow]Loading BFCL v4 dataset...[/yellow]")

    dataset = loader.load_external(
        "bfcl",
        dataset_path,
        categories=args.categories,
        max_per_category=args.max_per_category,
    )

    # Show dataset summary
    total_instances = sum(len(t.instances) for t in dataset.tasks)
    console.print(f"Loaded [cyan]{len(dataset.tasks)}[/cyan] tasks with [cyan]{total_instances}[/cyan] instances")

    if not dataset.tasks:
        console.print("[red]No tasks loaded. Check dataset path and categories.[/red]")
        sys.exit(1)

    # Build config
    config = BenchmarkConfig(
        dataset_name="bfcl_v4",
        baseline_name="direct_llm",
        max_instances=args.max_instances,
        output_dir=Path(args.output_dir),
    )

    # Run benchmark
    runner = BenchmarkRunner(datasets_dir="datasets")

    console.print("\n[yellow]Running benchmark...[/yellow]\n")

    result = runner.run_with_dataset(
        config,
        dataset,
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
    table = Table(title="BFCL Task Results")
    table.add_column("Category", style="cyan")
    table.add_column("Difficulty", style="magenta")
    table.add_column("Success Rate", justify="right")
    table.add_column("Avg Latency (ms)", justify="right")
    table.add_column("Instances", justify="right")

    for tr in result.task_results:
        # Extract category from task_id (bfcl_simple -> simple)
        category = tr.task.task_id.replace("bfcl_", "")
        difficulty = BFCLAdapter.CATEGORIES.get(category, {}).get("difficulty", "")

        success_style = "green" if tr.success_rate >= 0.8 else "yellow" if tr.success_rate >= 0.5 else "red"
        table.add_row(
            category,
            difficulty,
            f"[{success_style}]{tr.success_rate:.1%}[/{success_style}]",
            f"{tr.avg_latency_ms:.0f}",
            str(len(tr.results)),
        )

    console.print(table)

    # Show sample outputs
    console.print("\n[bold]Sample Outputs:[/bold]")
    for tr in result.task_results[:3]:
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

    if args.list_categories:
        list_categories(console)
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
