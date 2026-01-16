#!/usr/bin/env python3
"""Run the AgentBench dataset with the Direct LLM baseline.

AgentBench evaluates agent capabilities across 8 environments:
OS, DB, KG, ALFWorld, WebShop, Mind2Web, Avalon, and LTP.

Usage:
    python scripts/run_agentbench_benchmark.py --provider anthropic
    python scripts/run_agentbench_benchmark.py --provider gemini --environments os db
    python scripts/run_agentbench_benchmark.py --provider anthropic --split dev --max-per-env 10
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compiled_ai.runner import BenchmarkConfig, BenchmarkRunner, DatasetLoader
from compiled_ai.runner.loader import AgentBenchAdapter


# Available AgentBench environments
AGENTBENCH_ENVIRONMENTS = list(AgentBenchAdapter.ENVIRONMENTS.keys())


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run AgentBench with Direct LLM baseline"
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
        "--environments",
        nargs="+",
        choices=AGENTBENCH_ENVIRONMENTS,
        default=None,
        help=f"Environments to run (default: all). Choices: {', '.join(AGENTBENCH_ENVIRONMENTS)}",
    )
    parser.add_argument(
        "--split",
        choices=["dev", "test"],
        default="dev",
        help="Dataset split to use (default: dev)",
    )
    parser.add_argument(
        "--max-per-env",
        type=int,
        default=None,
        help="Maximum instances per environment",
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
        default="datasets/agentbench",
        help="Path to AgentBench dataset (default: datasets/agentbench)",
    )
    parser.add_argument(
        "--list-environments",
        action="store_true",
        help="List available environments and exit",
    )
    return parser.parse_args()


def list_environments(console: Console) -> None:
    """List all available AgentBench environments."""
    table = Table(title="AgentBench Environments")
    table.add_column("Environment", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Difficulty", style="magenta")
    table.add_column("Docker Required", justify="center")

    for env_id, config in AgentBenchAdapter.ENVIRONMENTS.items():
        docker_status = "[yellow]Yes[/yellow]" if config["requires_docker"] else "[green]No[/green]"
        table.add_row(
            env_id,
            config["name"],
            config["difficulty"],
            docker_status,
        )

    console.print(table)
    console.print("\n[dim]Note: Some environments require Docker for full execution.[/dim]")


def run_benchmark(args: argparse.Namespace, console: Console) -> None:
    """Run the benchmark with given arguments."""
    console.print("\n[bold blue]AgentBench Benchmark Runner[/bold blue]")
    console.print(f"Provider: [cyan]{args.provider}[/cyan]")
    if args.model:
        console.print(f"Model: [cyan]{args.model}[/cyan]")
    console.print(f"Split: [cyan]{args.split}[/cyan]")
    if args.environments:
        console.print(f"Environments: [cyan]{', '.join(args.environments)}[/cyan]")
    console.print()

    # Check if dataset exists
    dataset_path = Path(args.dataset_path)
    if not dataset_path.exists():
        console.print(f"[red]Error: Dataset not found at {dataset_path}[/red]")
        console.print("\nTo download AgentBench, run:")
        console.print("[cyan]  python scripts/download_agentbench.py[/cyan]")
        sys.exit(1)

    # Load dataset with adapter options
    loader = DatasetLoader("datasets")
    console.print("[yellow]Loading AgentBench dataset...[/yellow]")

    dataset = loader.load_external(
        "agentbench",
        dataset_path,
        environments=args.environments,
        split=args.split,
        max_per_env=args.max_per_env,
    )

    # Show dataset summary
    total_instances = sum(len(t.instances) for t in dataset.tasks)
    console.print(f"Loaded [cyan]{len(dataset.tasks)}[/cyan] tasks with [cyan]{total_instances}[/cyan] instances")

    if not dataset.tasks:
        console.print("[red]No tasks loaded. Check dataset path and environments.[/red]")
        console.print("\n[dim]Note: AgentBench data may need to be organized or some environments may not have data.[/dim]")
        sys.exit(1)

    # Check for Docker-required environments
    if args.environments:
        docker_envs = [
            env for env in args.environments
            if AgentBenchAdapter.ENVIRONMENTS.get(env, {}).get("requires_docker", False)
        ]
        if docker_envs:
            console.print(f"\n[yellow]Warning: Environments requiring Docker for full execution: {', '.join(docker_envs)}[/yellow]")
            console.print("[dim]Benchmark will run but may have limited evaluation accuracy.[/dim]\n")

    # Build config
    config = BenchmarkConfig(
        dataset_name="agentbench",
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
    table = Table(title="AgentBench Task Results")
    table.add_column("Environment", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Difficulty", style="magenta")
    table.add_column("Success Rate", justify="right")
    table.add_column("Avg Latency (ms)", justify="right")
    table.add_column("Instances", justify="right")

    for tr in result.task_results:
        # Extract environment from task_id (agentbench_os -> os)
        env_id = tr.task.task_id.replace("agentbench_", "")
        env_config = AgentBenchAdapter.ENVIRONMENTS.get(env_id, {})

        success_style = "green" if tr.success_rate >= 0.8 else "yellow" if tr.success_rate >= 0.5 else "red"
        table.add_row(
            env_id,
            env_config.get("name", env_id),
            env_config.get("difficulty", ""),
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

    if args.list_environments:
        list_environments(console)
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
