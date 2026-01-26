#!/usr/bin/env python3
"""Run the DocILE dataset with various baselines.

DocILE (Document Information Localization and Extraction) evaluates
document extraction capabilities on business documents (invoices, receipts).

Usage:
    python scripts/run_docile_benchmark.py --provider anthropic
    python scripts/run_docile_benchmark.py --provider gemini --task-type kile
    python scripts/run_docile_benchmark.py --provider anthropic --max-documents 50
    python scripts/run_docile_benchmark.py --baseline langchain --task-type kile
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compiled_ai.runner import BenchmarkConfig, BenchmarkRunner, DatasetLoader
from compiled_ai.baselines import list_baselines


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run DocILE with various baselines"
    )
    parser.add_argument(
        "--baseline",
        choices=list_baselines(),
        default="direct_llm",
        help=f"Baseline to run (default: direct_llm, available: {list_baselines()})",
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
        "--task-type",
        choices=["kile", "lir"],
        default="kile",
        help="Task type: 'kile' for key info extraction, 'lir' for line items (default: kile)",
    )
    parser.add_argument(
        "--split",
        choices=["train", "val", "test"],
        default=None,
        help="Dataset split to use (default: all available)",
    )
    parser.add_argument(
        "--max-documents",
        type=int,
        default=None,
        help="Maximum documents to process",
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
        default="datasets/docile",
        help="Path to DocILE dataset (default: datasets/docile)",
    )
    return parser.parse_args()


def run_benchmark(args: argparse.Namespace, console: Console) -> None:
    """Run the benchmark with given arguments."""
    console.print("\n[bold blue]DocILE Benchmark Runner[/bold blue]")
    console.print(f"Baseline: [cyan]{args.baseline}[/cyan]")
    console.print(f"Provider: [cyan]{args.provider}[/cyan]")
    if args.model:
        console.print(f"Model: [cyan]{args.model}[/cyan]")
    console.print(f"Task Type: [cyan]{args.task_type.upper()}[/cyan]")
    if args.split:
        console.print(f"Split: [cyan]{args.split}[/cyan]")
    console.print()

    # Check if dataset exists
    dataset_path = Path(args.dataset_path)
    if not dataset_path.exists():
        console.print(f"[red]Error: Dataset not found at {dataset_path}[/red]")
        console.print("\nTo download DocILE, run:")
        console.print("[cyan]  ./scripts/download_docile.sh YOUR_TOKEN[/cyan]")
        console.print("\nTo get your token:")
        console.print("  1. Visit https://docile.rossum.ai/")
        console.print("  2. Complete the Dataset Access Request form")
        console.print("  3. Receive your token via email")
        sys.exit(1)

    # Load dataset with adapter options
    loader = DatasetLoader("datasets")
    console.print("[yellow]Loading DocILE dataset...[/yellow]")

    dataset = loader.load_external(
        "docile",
        dataset_path,
        task_type=args.task_type,
        split=args.split,
        max_documents=args.max_documents,
    )

    # Show dataset summary
    total_instances = sum(len(t.instances) for t in dataset.tasks)
    console.print(f"Loaded [cyan]{len(dataset.tasks)}[/cyan] tasks with [cyan]{total_instances}[/cyan] instances")

    if not dataset.tasks:
        console.print("[red]No tasks loaded. Check dataset path and task type.[/red]")
        sys.exit(1)

    # Build config
    config = BenchmarkConfig(
        dataset_name="docile",
        baseline_name=args.baseline,
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
    table = Table(title="DocILE Task Results")
    table.add_column("Task", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Difficulty", style="magenta")
    table.add_column("Success Rate", justify="right")
    table.add_column("Avg Latency (ms)", justify="right")
    table.add_column("Instances", justify="right")

    for tr in result.task_results:
        success_style = "green" if tr.success_rate >= 0.8 else "yellow" if tr.success_rate >= 0.5 else "red"
        table.add_row(
            tr.task.name,
            args.task_type.upper(),
            tr.task.difficulty.value,
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
