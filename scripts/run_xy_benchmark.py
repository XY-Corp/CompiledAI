#!/usr/bin/env python3
"""Run the XY_Benchmark dataset with various baselines.

Usage:
    python scripts/run_xy_benchmark.py --baseline direct_llm --provider anthropic
    python scripts/run_xy_benchmark.py --baseline langchain --provider anthropic
    python scripts/run_xy_benchmark.py --provider gemini --max-instances 2
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
        description="Run XY_Benchmark with specified baseline"
    )
    parser.add_argument(
        "--baseline",
        choices=["direct_llm", "code_factory"],
        default="direct_llm",
        help="Baseline to use (default: direct_llm)",
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
    console.print(f"Baseline: [cyan]{args.baseline}[/cyan]")
    console.print(f"Provider: [cyan]{args.provider}[/cyan]")
    if args.model:
        console.print(f"Model: [cyan]{args.model}[/cyan]")
    console.print()

    # Build config
    config = BenchmarkConfig(
        dataset_name="xy_benchmark",
        baseline_name=args.baseline,
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

    # Show Code Factory specific metrics (generation vs execution time)
    if args.baseline == "code_factory":
        console.print("\n[bold cyan]Code Factory Metrics:[/bold cyan]")

        cf_table = Table(title="Compilation vs Execution Time")
        cf_table.add_column("Task ID", style="cyan")
        cf_table.add_column("Generation (ms)", justify="right", style="yellow")
        cf_table.add_column("Execution (ms)", justify="right", style="green")
        cf_table.add_column("Speedup", justify="right", style="magenta")

        for tr in result.task_results:
            # Find first result with generation time (compilation task)
            gen_times = [r.generation_time_ms for r in tr.results if r.generation_time_ms]
            avg_gen = sum(gen_times) / len(gen_times) if gen_times else 0

            # Average execution time across all tasks
            exec_times = [r.execution_time_ms for r in tr.results if r.execution_time_ms]
            avg_exec = sum(exec_times) / len(exec_times) if exec_times else 0

            # Calculate speedup (how much faster execution is vs compilation)
            speedup = f"{avg_gen / avg_exec:.1f}x" if avg_exec > 0 and avg_gen > 0 else "-"

            cf_table.add_row(
                tr.task.task_id,
                f"{avg_gen:.0f}" if avg_gen > 0 else "-",
                f"{avg_exec:.0f}",
                speedup,
            )

        console.print(cf_table)

    # Show all failing tasks with output comparison
    failing_tasks = [tr for tr in result.task_results if tr.success_rate < 1.0]
    if failing_tasks:
        console.print("\n[bold red]Failing Tasks (with output comparison):[/bold red]")
        for tr in failing_tasks:
            if tr.logs:
                first_log = tr.logs[0]
                console.print(f"\n[cyan]{tr.task.task_id}[/cyan] (success rate: {tr.success_rate:.0%}):")
                console.print(f"  [red]✗ Failed[/red]")
                if first_log.error:
                    console.print(f"  Error: [red]{first_log.error}[/red]")
                console.print(f"  Expected: [green]{first_log.expected_output}[/green]")
                console.print(f"  Actual:   [yellow]{first_log.output}[/yellow]")

    # Show sample successful outputs
    successful_tasks = [tr for tr in result.task_results if tr.success_rate == 1.0]
    if successful_tasks:
        console.print("\n[bold green]Sample Successful Outputs:[/bold green]")
        for tr in successful_tasks[:3]:  # Show first 3 successful
            if tr.logs:
                first_log = tr.logs[0]
                console.print(f"\n[cyan]{tr.task.task_id}[/cyan]:")
                console.print(f"  [green]✓ Success[/green]")
                output_preview = first_log.output[:200] + "..." if len(first_log.output) > 200 else first_log.output
                console.print(f"  Output: {output_preview}")

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
