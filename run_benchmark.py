#!/usr/bin/env python3
"""Interactive benchmark runner for Compiled AI.

Usage:
    # Interactive mode
    python run_benchmark.py

    # Direct mode with parameters
    python run_benchmark.py --dataset xy_benchmark --provider anthropic
    python run_benchmark.py --dataset bfcl --categories simple multiple --max-instances 10
    python run_benchmark.py --dataset agentbench --environments os --split dev
"""

import argparse
import sys
from pathlib import Path

import questionary
from questionary import Style as QStyle
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text
from rich import box

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent / "src"))

from compiled_ai.runner import BenchmarkConfig, BenchmarkRunner, DatasetLoader
from compiled_ai.runner.loader import AgentBenchAdapter, BFCLAdapter

console = Console()

# Brand colors - XY.AI palette
BRAND_PRIMARY = "#5f819d"      # Muted blue-gray
BRAND_SECONDARY = "#b5bd68"    # Muted olive/green
BRAND_ACCENT = "#5f819d"       # Same as primary for highlights
BRAND_SUCCESS = "#b5bd68"      # Same as secondary for consistency
BRAND_ERROR = "#cc6666"        # Muted red
BRAND_DIM = "dim"

# Questionary custom style (matching brand colors)
QUESTIONARY_STYLE = QStyle([
    ('qmark', 'fg:#5f819d bold'),         # Question mark
    ('question', 'fg:white bold'),         # Question text
    ('answer', 'fg:#b5bd68 bold'),         # Selected answer
    ('pointer', 'fg:#5f819d bold'),        # Selection pointer (>)
    ('highlighted', 'fg:#5f819d bold'),    # Highlighted choice
    ('selected', 'fg:#b5bd68'),            # Selected items (checkbox)
    ('separator', 'fg:#666666'),           # Separator
    ('instruction', 'fg:#888888'),         # Instructions
    ('text', 'fg:white'),                  # Default text
])

# ASCII Art Logo
LOGO = """
[#5f819d]██╗  ██╗██╗   ██╗[/#5f819d]   [#b5bd68]██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗[/#b5bd68]
[#5f819d]╚██╗██╔╝╚██╗ ██╔╝[/#5f819d]   [#b5bd68]██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║[/#b5bd68]
[#5f819d] ╚███╔╝  ╚████╔╝ [/#5f819d]   [#b5bd68]██████╔╝█████╗  ██╔██╗ ██║██║     ███████║[/#b5bd68]
[#5f819d] ██╔██╗   ╚██╔╝  [/#5f819d]   [#b5bd68]██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║[/#b5bd68]
[#5f819d]██╔╝ ██╗   ██║   [/#5f819d]   [#b5bd68]██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║[/#b5bd68]
[#5f819d]╚═╝  ╚═╝   ╚═╝   [/#5f819d]   [#b5bd68]╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝[/#b5bd68]
"""

TAGLINE = "[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]"

# Dataset configurations
DATASETS = {
    "xy_benchmark": {
        "name": "XY Benchmark",
        "description": "Internal benchmark (classification, normalization, function calling)",
        "path": "datasets/xy_benchmark",
        "type": "internal",
        "icon": "🎯",
    },
    "bfcl": {
        "name": "BFCL v4",
        "description": "Berkeley Function Calling Leaderboard",
        "path": "datasets/bfcl_v4",
        "type": "external",
        "adapter": "bfcl",
        "categories": list(BFCLAdapter.CATEGORIES.keys()),
        "icon": "📞",
    },
    "agentbench": {
        "name": "AgentBench",
        "description": "Multi-turn agent benchmark (8 environments)",
        "path": "datasets/agentbench",
        "type": "external",
        "adapter": "agentbench",
        "environments": list(AgentBenchAdapter.ENVIRONMENTS.keys()),
        "icon": "🤖",
    },
}

PROVIDERS = {
    "anthropic": {"name": "Anthropic", "icon": "🅰️", "model": "Claude"},
    "openai": {"name": "OpenAI", "icon": "🟢", "model": "GPT-4"},
    "gemini": {"name": "Google", "icon": "🔷", "model": "Gemini"},
}

BASELINES = {
    "direct_llm": {
        "name": "Direct LLM",
        "description": "Per-transaction inference (no compilation)",
        "icon": "⚡",
    },
    "code_factory": {
        "name": "Code Factory",
        "description": "Compiled workflow with template-assisted generation",
        "icon": "🏭",
    },
    # Future baselines:
    # "langchain": {
    #     "name": "LangChain",
    #     "description": "LangChain agent baseline",
    #     "icon": "🦜",
    # },
}


def print_header() -> None:
    """Print the branded header."""
    console.print()
    console.print(LOGO)
    console.print(TAGLINE)
    console.print()


def print_section(title: str) -> None:
    """Print a section header."""
    console.print(f"\n[{BRAND_PRIMARY}]▸ {title}[/{BRAND_PRIMARY}]")


def check_dataset_exists(dataset_key: str) -> bool:
    """Check if dataset is downloaded."""
    path = Path(DATASETS[dataset_key]["path"])
    return path.exists() and any(path.iterdir())


def list_datasets() -> None:
    """Display available datasets."""
    table = Table(
        title=f"[{BRAND_PRIMARY}]Available Datasets[/{BRAND_PRIMARY}]",
        box=box.ROUNDED,
        border_style=BRAND_DIM,
        title_style=f"bold {BRAND_PRIMARY}",
    )
    table.add_column("#", style=BRAND_ACCENT, justify="center", width=3)
    table.add_column("", justify="center", width=3)  # Icon
    table.add_column("Dataset", style=BRAND_PRIMARY)
    table.add_column("Description", style="white")
    table.add_column("Status", justify="center")

    for i, (key, info) in enumerate(DATASETS.items(), 1):
        exists = check_dataset_exists(key)
        status = f"[{BRAND_SUCCESS}]● Ready[/{BRAND_SUCCESS}]" if exists else f"[{BRAND_ERROR}]○ Missing[/{BRAND_ERROR}]"
        table.add_row(str(i), info.get("icon", ""), info["name"], info["description"], status)

    console.print(table)


def list_providers() -> None:
    """Display available providers."""
    table = Table(
        title=f"[{BRAND_PRIMARY}]LLM Providers[/{BRAND_PRIMARY}]",
        box=box.ROUNDED,
        border_style=BRAND_DIM,
        title_style=f"bold {BRAND_PRIMARY}",
    )
    table.add_column("#", style=BRAND_ACCENT, justify="center", width=3)
    table.add_column("", justify="center", width=3)  # Icon
    table.add_column("Provider", style=BRAND_PRIMARY)
    table.add_column("Model", style="white")

    for i, (key, info) in enumerate(PROVIDERS.items(), 1):
        table.add_row(str(i), info["icon"], info["name"], info["model"])

    console.print(table)


def interactive_select_dataset() -> str | None:
    """Interactively select a dataset using arrow keys."""
    print_section("Select Dataset")
    console.print()

    # Build choices with icons and status
    choices = []
    for key, info in DATASETS.items():
        exists = check_dataset_exists(key)
        status = "● Ready" if exists else "○ Missing"
        label = f"{info.get('icon', '')}  {info['name']} - {info['description']} [{status}]"
        choices.append(questionary.Choice(title=label, value=key, disabled=None if exists else "Not downloaded"))

    choices.append(questionary.Separator())
    choices.append(questionary.Choice(title="✕  Exit", value=None))

    dataset_key = questionary.select(
        "Choose a dataset:",
        choices=choices,
        style=QUESTIONARY_STYLE,
        instruction="(Use ↑↓ arrows, Enter to select)",
    ).ask()

    if dataset_key is None:
        return None

    if not check_dataset_exists(dataset_key):
        console.print(f"\n[{BRAND_ERROR}]✗ Dataset '{dataset_key}' is not downloaded.[/{BRAND_ERROR}]")
        if dataset_key == "bfcl":
            console.print(f"  [{BRAND_DIM}]Run:[/{BRAND_DIM}] [{BRAND_PRIMARY}]python scripts/download_bfcl.py[/{BRAND_PRIMARY}]")
        elif dataset_key == "agentbench":
            console.print(f"  [{BRAND_DIM}]Run:[/{BRAND_DIM}] [{BRAND_PRIMARY}]python scripts/download_agentbench.py[/{BRAND_PRIMARY}]")
        return None

    return dataset_key


def interactive_select_provider() -> str:
    """Interactively select LLM provider using arrow keys."""
    print_section("Select Provider")
    console.print()

    choices = []
    for key, info in PROVIDERS.items():
        label = f"{info['icon']}  {info['name']} ({info['model']})"
        choices.append(questionary.Choice(title=label, value=key))

    provider = questionary.select(
        "Choose LLM provider:",
        choices=choices,
        style=QUESTIONARY_STYLE,
        instruction="(Use ↑↓ arrows, Enter to select)",
    ).ask()

    return provider or "anthropic"


def interactive_select_baseline() -> str:
    """Interactively select baseline using arrow keys."""
    print_section("Select Baseline")
    console.print()

    choices = []
    for key, info in BASELINES.items():
        label = f"{info['icon']}  {info['name']} - {info['description']}"
        choices.append(questionary.Choice(title=label, value=key))

    baseline = questionary.select(
        "Choose baseline:",
        choices=choices,
        style=QUESTIONARY_STYLE,
        instruction="(Use ↑↓ arrows, Enter to select)",
    ).ask()

    return baseline or "direct_llm"


def interactive_configure_dataset(dataset_key: str) -> dict:
    """Get dataset-specific configuration interactively using arrow keys."""
    config = {}
    dataset_info = DATASETS[dataset_key]

    if dataset_key == "bfcl":
        print_section("BFCL Configuration")
        console.print()

        categories = dataset_info["categories"]

        # Build checkbox choices with difficulty indicators
        choices = []
        for cat in categories:
            diff = BFCLAdapter.CATEGORIES[cat]["difficulty"]
            diff_icon = "🟢" if diff == "simple" else "🟡" if diff == "medium" else "🔴"
            label = f"{diff_icon} {cat} ({diff})"
            choices.append(questionary.Choice(title=label, value=cat, checked=True))

        selected = questionary.checkbox(
            "Select categories:",
            choices=choices,
            style=QUESTIONARY_STYLE,
            instruction="(Space to toggle, Enter to confirm)",
        ).ask()

        if selected and len(selected) < len(categories):
            config["categories"] = selected

        # Max per category
        max_per = questionary.text(
            "Max instances per category:",
            default="50",
            style=QUESTIONARY_STYLE,
        ).ask()
        if max_per and max_per.isdigit() and int(max_per) > 0:
            config["max_per_category"] = int(max_per)

    elif dataset_key == "agentbench":
        print_section("AgentBench Configuration")
        console.print()

        environments = dataset_info["environments"]

        # Build checkbox choices with docker indicators
        choices = []
        for env in environments:
            env_info = AgentBenchAdapter.ENVIRONMENTS[env]
            docker_icon = "🐳" if env_info["requires_docker"] else "  "
            label = f"{docker_icon} {env} - {env_info['name']}"
            choices.append(questionary.Choice(title=label, value=env, checked=True))

        selected = questionary.checkbox(
            "Select environments:",
            choices=choices,
            style=QUESTIONARY_STYLE,
            instruction="(Space to toggle, Enter to confirm)",
        ).ask()

        if selected and len(selected) < len(environments):
            config["environments"] = selected

        # Split selection
        split = questionary.select(
            "Choose split:",
            choices=[
                questionary.Choice(title="📊 dev (development set)", value="dev"),
                questionary.Choice(title="🧪 test (test set)", value="test"),
            ],
            style=QUESTIONARY_STYLE,
            instruction="(Use ↑↓ arrows, Enter to select)",
        ).ask()
        config["split"] = split or "dev"

        # Max per environment
        max_per = questionary.text(
            "Max instances per environment:",
            default="20",
            style=QUESTIONARY_STYLE,
        ).ask()
        if max_per and max_per.isdigit() and int(max_per) > 0:
            config["max_per_env"] = int(max_per)

    return config


def run_benchmark_interactive() -> None:
    """Run benchmark in interactive mode."""
    print_header()

    # Select dataset
    dataset_key = interactive_select_dataset()
    if not dataset_key:
        console.print(f"\n[{BRAND_DIM}]Exiting...[/{BRAND_DIM}]")
        return

    # Select baseline
    baseline = interactive_select_baseline()

    # Select provider
    provider = interactive_select_provider()

    # Dataset-specific config
    dataset_config = interactive_configure_dataset(dataset_key)

    # Max instances
    print_section("Execution Options")
    console.print()

    max_instances_str = questionary.text(
        "Max instances per task (0 = all):",
        default="0",
        style=QUESTIONARY_STYLE,
    ).ask()

    max_instances = int(max_instances_str) if max_instances_str and max_instances_str.isdigit() else 0
    if max_instances == 0:
        max_instances = None

    # Confirm
    print_section("Configuration Summary")
    console.print()

    summary = Table(box=box.ROUNDED, show_header=False, border_style=BRAND_DIM)
    summary.add_column("Key", style=BRAND_DIM)
    summary.add_column("Value", style=BRAND_PRIMARY)

    summary.add_row("Dataset", f"{DATASETS[dataset_key]['icon']} {DATASETS[dataset_key]['name']}")
    summary.add_row("Baseline", f"{BASELINES[baseline]['icon']} {BASELINES[baseline]['name']}")
    summary.add_row("Provider", f"{PROVIDERS[provider]['icon']} {PROVIDERS[provider]['name']}")

    if dataset_config:
        for k, v in dataset_config.items():
            summary.add_row(k.replace("_", " ").title(), str(v))

    if max_instances:
        summary.add_row("Max Instances", str(max_instances))

    console.print(summary)
    console.print()

    confirm = questionary.confirm(
        "Start benchmark?",
        default=True,
        style=QUESTIONARY_STYLE,
    ).ask()

    if not confirm:
        console.print(f"\n[{BRAND_DIM}]Cancelled.[/{BRAND_DIM}]")
        return

    # Run
    # Enable verbose mode for code_factory to see logs
    verbose = baseline == "code_factory"
    run_benchmark(
        dataset_key=dataset_key,
        baseline=baseline,
        provider=provider,
        max_instances=max_instances,
        verbose=verbose,
        **dataset_config,
    )


def run_benchmark(
    dataset_key: str,
    baseline: str = "direct_llm",
    provider: str = "anthropic",
    model: str | None = None,
    max_instances: int | None = None,
    enable_cache: bool = False,
    verbose: bool = False,
    output_dir: str = "results",
    **dataset_kwargs,
) -> None:
    """Run benchmark with given configuration."""
    print_section(f"Running {DATASETS[dataset_key]['name']}")
    console.print()

    info_text = Text()
    info_text.append("  Baseline: ", style=BRAND_DIM)
    info_text.append(f"{BASELINES[baseline]['icon']} {BASELINES[baseline]['name']}\n", style=BRAND_PRIMARY)
    info_text.append("  Provider: ", style=BRAND_DIM)
    info_text.append(f"{PROVIDERS[provider]['icon']} {PROVIDERS[provider]['name']}\n", style=BRAND_PRIMARY)
    if model:
        info_text.append("  Model: ", style=BRAND_DIM)
        info_text.append(f"{model}\n", style=BRAND_PRIMARY)
    console.print(info_text)

    dataset_info = DATASETS[dataset_key]
    loader = DatasetLoader("datasets")

    # Load dataset
    console.print(f"  [{BRAND_DIM}]Loading dataset...[/{BRAND_DIM}]", end="")

    if dataset_info["type"] == "internal":
        dataset = loader.load(dataset_key)
    else:
        dataset = loader.load_external(
            dataset_info["adapter"],
            dataset_info["path"],
            **dataset_kwargs,
        )

    total_instances = sum(len(t.instances) for t in dataset.tasks)
    console.print(f" [{BRAND_SUCCESS}]✓[/{BRAND_SUCCESS}]")
    console.print(f"  [{BRAND_DIM}]Loaded[/{BRAND_DIM}] [{BRAND_PRIMARY}]{len(dataset.tasks)}[/{BRAND_PRIMARY}] [{BRAND_DIM}]tasks with[/{BRAND_DIM}] [{BRAND_PRIMARY}]{total_instances}[/{BRAND_PRIMARY}] [{BRAND_DIM}]instances[/{BRAND_DIM}]")

    if not dataset.tasks:
        console.print(f"\n[{BRAND_ERROR}]✗ No tasks loaded.[/{BRAND_ERROR}]")
        return

    # Build config
    config = BenchmarkConfig(
        dataset_name=dataset_key,
        baseline_name=baseline,
        max_instances=max_instances,
        output_dir=Path(output_dir),
    )

    # Run
    console.print(f"\n  [{BRAND_ACCENT}]Running benchmark...[/{BRAND_ACCENT}]\n")

    runner = BenchmarkRunner(datasets_dir="datasets")

    result = runner.run_with_dataset(
        config,
        dataset,
        provider=provider,
        model=model,
        enable_cache=enable_cache,
        verbose=verbose,
    )

    # Display results
    display_results(result)


def display_results(result) -> None:
    """Display benchmark results."""
    print_section("Results")
    console.print()

    # Summary panel
    success_rate = result.overall_success_rate
    rate_color = BRAND_SUCCESS if success_rate >= 0.8 else BRAND_ACCENT if success_rate >= 0.5 else BRAND_ERROR

    summary_text = Text()
    summary_text.append("Duration: ", style=BRAND_DIM)
    summary_text.append(f"{result.duration_seconds:.2f}s\n", style=BRAND_PRIMARY)
    summary_text.append("Success Rate: ", style=BRAND_DIM)
    summary_text.append(f"{success_rate:.1%}", style=f"bold {rate_color}")

    console.print(Panel(
        summary_text,
        title=f"[{BRAND_PRIMARY}]Summary[/{BRAND_PRIMARY}]",
        border_style=rate_color,
        box=box.ROUNDED,
    ))

    # Task-level results
    console.print()
    table = Table(
        title=f"[{BRAND_PRIMARY}]Task Results[/{BRAND_PRIMARY}]",
        box=box.ROUNDED,
        border_style=BRAND_DIM,
        title_style=f"bold {BRAND_PRIMARY}",
    )
    table.add_column("Task", style=BRAND_PRIMARY)
    table.add_column("Success", justify="center")
    table.add_column("Latency", justify="right", style=BRAND_DIM)

    # Add Code Factory specific columns
    is_code_factory = result.config.baseline_name == "code_factory"
    if is_code_factory:
        table.add_column("Gen (ms)", justify="right", style="yellow")
        table.add_column("Exec (ms)", justify="right", style="green")

    table.add_column("N", justify="right", style=BRAND_DIM)

    for tr in result.task_results:
        rate = tr.success_rate
        rate_style = BRAND_SUCCESS if rate >= 0.8 else BRAND_ACCENT if rate >= 0.5 else BRAND_ERROR

        # Create a visual bar
        bar_filled = int(rate * 10)
        bar_empty = 10 - bar_filled
        bar = f"[{rate_style}]{'█' * bar_filled}[/{rate_style}][{BRAND_DIM}]{'░' * bar_empty}[/{BRAND_DIM}] [{rate_style}]{rate:.0%}[/{rate_style}]"

        # Build row data
        row_data = [
            tr.task.task_id,
            bar,
            f"{tr.avg_latency_ms:.0f}ms",
        ]

        # Add Code Factory metrics if applicable
        if is_code_factory:
            # Calculate average generation and execution times
            gen_times = [r.generation_time_ms for r in tr.results if r.generation_time_ms]
            avg_gen = sum(gen_times) / len(gen_times) if gen_times else 0

            exec_times = [r.execution_time_ms for r in tr.results if r.execution_time_ms]
            avg_exec = sum(exec_times) / len(exec_times) if exec_times else 0

            row_data.append(f"{avg_gen:.0f}" if avg_gen > 0 else "-")
            row_data.append(f"{avg_exec:.0f}" if avg_exec > 0 else "-")

        row_data.append(str(len(tr.results)))

        table.add_row(*row_data)

    console.print(table)

    # Show Activity Accuracy Registry (Code Factory only)
    if is_code_factory:
        try:
            from compiled_ai.factory.code_factory.activity_registry import ActivityRegistry

            registry = ActivityRegistry()
            all_stats = registry.get_all_stats()

            if all_stats:
                console.print(f"\n[bold {BRAND_PRIMARY}]Activity Accuracy Registry:[/bold {BRAND_PRIMARY}]")

                acc_table = Table(
                    title=f"[{BRAND_PRIMARY}]Workflow Reliability[/{BRAND_PRIMARY}]",
                    box=box.ROUNDED,
                    border_style=BRAND_DIM,
                )
                acc_table.add_column("Workflow ID", style=BRAND_PRIMARY)
                acc_table.add_column("Category", style=BRAND_DIM)
                acc_table.add_column("Success Rate", justify="center")
                acc_table.add_column("Usage", justify="right", style=BRAND_DIM)
                acc_table.add_column("Last Used", style=BRAND_DIM)

                for stats in all_stats:
                    # Color-code success rate
                    rate = stats.success_rate
                    if rate >= 0.9:
                        rate_color = BRAND_SUCCESS
                        rate_icon = "✓"
                    elif rate >= 0.7:
                        rate_color = BRAND_ACCENT
                        rate_icon = "~"
                    else:
                        rate_color = BRAND_ERROR
                        rate_icon = "✗"

                    rate_display = f"[{rate_color}]{rate_icon} {rate:.0%}[/{rate_color}]"

                    # Format last used
                    last_used = stats.last_used if stats.last_used else "Never"
                    if last_used != "Never":
                        # Show relative time
                        from datetime import datetime
                        try:
                            dt = datetime.fromisoformat(last_used)
                            last_used = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            pass

                    acc_table.add_row(
                        stats.workflow_id,
                        stats.category,
                        rate_display,
                        f"{stats.usage_count}x",
                        last_used,
                    )

                console.print(acc_table)
        except Exception as e:
            # Silently fail if registry not available
            pass

    # Show detailed output for ALL tasks
    print_section("Detailed Task Outputs")
    for tr in result.task_results:
        if tr.logs:
            first_log = tr.logs[0]
            status_icon = f"[{BRAND_SUCCESS}]✓[/{BRAND_SUCCESS}]" if first_log.success else f"[{BRAND_ERROR}]✗[/{BRAND_ERROR}]"

            console.print(f"\n  {status_icon} [{BRAND_PRIMARY}]{tr.task.task_id}[/{BRAND_PRIMARY}] [{BRAND_DIM}](success rate: {tr.success_rate:.0%})[/{BRAND_DIM}]")

            if first_log.error:
                console.print(f"    [{BRAND_DIM}]Error:[/{BRAND_DIM}] [{BRAND_ERROR}]{first_log.error}[/{BRAND_ERROR}]")

            console.print(f"    [{BRAND_DIM}]Expected:[/{BRAND_DIM}] [{BRAND_SUCCESS}]{first_log.expected_output}[/{BRAND_SUCCESS}]")
            console.print(f"    [{BRAND_DIM}]Actual:[/{BRAND_DIM}]   [{BRAND_ACCENT}]{first_log.output}[/{BRAND_ACCENT}]")

    console.print(f"\n  [{BRAND_DIM}]Results saved to:[/{BRAND_DIM}] [{BRAND_PRIMARY}]{result.config.output_dir}/[/{BRAND_PRIMARY}]\n")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="XY Bench - LLM Evaluation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_benchmark.py                                    # Interactive mode
  python run_benchmark.py --dataset xy_benchmark             # Run XY Benchmark
  python run_benchmark.py --dataset bfcl --categories simple # Run BFCL simple
  python run_benchmark.py --dataset agentbench --environments os db
  python run_benchmark.py --list                             # List datasets
        """,
    )

    parser.add_argument(
        "--dataset", "-d",
        choices=list(DATASETS.keys()),
        help="Dataset to run",
    )
    parser.add_argument(
        "--baseline", "-b",
        choices=list(BASELINES.keys()),
        default="direct_llm",
        help="Baseline to run (default: direct_llm)",
    )
    parser.add_argument(
        "--provider", "-p",
        choices=list(PROVIDERS.keys()),
        default="anthropic",
        help="LLM provider (default: anthropic)",
    )
    parser.add_argument(
        "--model", "-m",
        help="Model name (default: provider's default)",
    )
    parser.add_argument(
        "--max-instances",
        type=int,
        help="Max instances per task",
    )
    parser.add_argument(
        "--enable-cache",
        action="store_true",
        help="Enable response caching",
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Output directory (default: results)",
    )

    # BFCL options
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=list(BFCLAdapter.CATEGORIES.keys()),
        help="BFCL categories to run",
    )
    parser.add_argument(
        "--max-per-category",
        type=int,
        help="Max instances per BFCL category",
    )

    # AgentBench options
    parser.add_argument(
        "--environments",
        nargs="+",
        choices=list(AgentBenchAdapter.ENVIRONMENTS.keys()),
        help="AgentBench environments to run",
    )
    parser.add_argument(
        "--split",
        choices=["dev", "test"],
        default="dev",
        help="AgentBench split (default: dev)",
    )
    parser.add_argument(
        "--max-per-env",
        type=int,
        help="Max instances per AgentBench environment",
    )

    # Utility
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available datasets and exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging (shows detailed execution logs)",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Skip printing the header/logo",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    if args.list:
        print_header()
        list_datasets()
        console.print()
        return

    if args.dataset:
        # Direct mode with parameters
        if not args.no_header:
            print_header()

        if not check_dataset_exists(args.dataset):
            console.print(f"[{BRAND_ERROR}]✗ Dataset '{args.dataset}' not found.[/{BRAND_ERROR}]")
            if args.dataset == "bfcl":
                console.print(f"  [{BRAND_DIM}]Run:[/{BRAND_DIM}] [{BRAND_PRIMARY}]python scripts/download_bfcl.py[/{BRAND_PRIMARY}]")
            elif args.dataset == "agentbench":
                console.print(f"  [{BRAND_DIM}]Run:[/{BRAND_DIM}] [{BRAND_PRIMARY}]python scripts/download_agentbench.py[/{BRAND_PRIMARY}]")
            sys.exit(1)

        # Build dataset kwargs
        dataset_kwargs = {}
        if args.categories:
            dataset_kwargs["categories"] = args.categories
        if args.max_per_category:
            dataset_kwargs["max_per_category"] = args.max_per_category
        if args.environments:
            dataset_kwargs["environments"] = args.environments
        if args.split:
            dataset_kwargs["split"] = args.split
        if args.max_per_env:
            dataset_kwargs["max_per_env"] = args.max_per_env

        try:
            run_benchmark(
                dataset_key=args.dataset,
                baseline=args.baseline,
                provider=args.provider,
                model=args.model,
                max_instances=args.max_instances,
                enable_cache=args.enable_cache,
                verbose=args.verbose,
                output_dir=args.output_dir,
                **dataset_kwargs,
            )
        except KeyboardInterrupt:
            console.print(f"\n[{BRAND_ACCENT}]Interrupted.[/{BRAND_ACCENT}]")
            sys.exit(1)
    else:
        # Interactive mode
        try:
            run_benchmark_interactive()
        except KeyboardInterrupt:
            console.print(f"\n\n[{BRAND_DIM}]Exiting...[/{BRAND_DIM}]")
            sys.exit(0)


if __name__ == "__main__":
    main()
