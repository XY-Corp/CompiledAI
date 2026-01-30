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

from compiled_ai.datasets import (
    BFCLConverter,
    XYConverter,
    SecurityFixtureConverter,
    DatasetInstance,
    run_benchmark as run_simple_benchmark,
    BenchmarkResult as SimpleBenchmarkResult,
    InstanceResult,
)
from compiled_ai.datasets.docile_converter import DocILEConverter
from compiled_ai.datasets.eltbench_converter import ELTBenchConverter
from compiled_ai.baselines.base import get_baseline
from compiled_ai.runner.loader import AgentBenchAdapter, BFCLAdapter  # For category info only

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
    "security_benchmark": {
        "name": "Security Benchmark",
        "description": "Security validation tests (injection, PII, code safety)",
        "path": "datasets/security_benchmark",
        "type": "internal",
        "icon": "🔒",
    },
    "security_input_gate": {
        "name": "Security Input Gate",
        "description": "INPUT GATE tests (prompt injection, PII detection) - 55 instances",
        "path": "datasets/security_benchmark/tasks/input_gate",
        "type": "internal",
        "icon": "🛡️",
    },
    "security_code_gate": {
        "name": "Security Code Gate",
        "description": "CODE GATE tests (tricky prompts that lead to unsafe code generation)",
        "path": "datasets/security_benchmark/tasks/code_gate",
        "type": "internal",
        "icon": "🔧",
    },
    "security_code_gate_fixtures": {
        "name": "Security Code Gate Fixtures",
        "description": "CODE GATE fixture tests (pre-made vulnerable workflows for deterministic testing)",
        "path": "workflows",
        "type": "fixtures",
        "icon": "🧪",
    },
    "security_output_gate": {
        "name": "Security Output Gate",
        "description": "OUTPUT GATE tests (system prompt leakage via canary tokens) - 20 instances",
        "path": "datasets/security_benchmark/tasks/output_gate",
        "type": "internal",
        "icon": "🔐",
        "baseline_kwargs": {
            "enable_output_gate": True,
        },
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
    "docile_kile": {
        "name": "DocILE KILE",
        "description": "Document key information extraction (invoice headers)",
        "path": "datasets/benchmarks/DocILE",
        "type": "external",
        "task_type": "kile",
        "icon": "📄",
        "baseline_kwargs": {
            "enable_security": False,  # Disable INPUT GATE - OCR text triggers false positives
        },
    },
    "docile_lir": {
        "name": "DocILE LIR",
        "description": "Document line item recognition (invoice tables)",
        "path": "datasets/benchmarks/DocILE",
        "type": "external",
        "task_type": "lir",
        "icon": "📋",
        "baseline_kwargs": {
            "enable_security": False,  # Disable INPUT GATE - OCR text triggers false positives
        },
    },
    "eltbench": {
        "name": "ELT-Bench",
        "description": "ELT pipeline SQL generation (100 tasks)",
        "path": "datasets/benchmarks/ELT-Bench",
        "type": "external",
        "icon": "🔄",
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
    max_tasks: int | None = None,
    enable_cache: bool = False,
    verbose: bool = False,
    output_dir: str = "results",
    **dataset_kwargs,
) -> None:
    """Run benchmark with given configuration.

    Uses the new generic DatasetInstance format:
    - Load via converters → {input, possible_outputs}
    - Run baseline → output
    - Evaluate via instance.matches(output)

    No evaluators, no transformers, no complexity.
    """
    import json
    from datetime import datetime

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

    # Create unique run directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path("logs") / f"run_{timestamp}_{baseline}_{dataset_key}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Create config file for this run
    config = {
        "timestamp": timestamp,
        "baseline": baseline,
        "dataset": dataset_key,
        "provider": provider,
        "model": model,
        "max_instances": max_instances,
        "max_tasks": max_tasks,
        "enable_cache": enable_cache,
        "verbose": verbose,
        "dataset_kwargs": dataset_kwargs,
    }

    config_path = run_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    console.print(f"  [{BRAND_DIM}]Run directory:[/{BRAND_DIM}] [{BRAND_PRIMARY}]{run_dir}[/{BRAND_PRIMARY}]")
    console.print()

    dataset_info = DATASETS[dataset_key]

    # Load dataset using NEW converters
    console.print(f"  [{BRAND_DIM}]Loading dataset...[/{BRAND_DIM}]", end="")

    instances: list[DatasetInstance] = []

    if dataset_key == "bfcl":
        converter = BFCLConverter()
        bfcl_path = Path(dataset_info["path"])

        # Get categories to load
        categories = dataset_kwargs.get("categories", list(BFCLAdapter.CATEGORIES.keys()))
        max_per_cat = dataset_kwargs.get("max_per_category")

        for cat in categories:
            cat_info = BFCLAdapter.CATEGORIES.get(cat, {})
            filename = cat_info.get("file", f"BFCL_v3_{cat}.json")
            file_path = bfcl_path / filename

            if file_path.exists():
                cat_instances = converter.load_file(str(file_path))
                if max_per_cat:
                    cat_instances = cat_instances[:max_per_cat]
                instances.extend(cat_instances)

    elif dataset_key in ("xy_benchmark", "security_benchmark", "security_input_gate", "security_code_gate", "security_output_gate"):
        converter = XYConverter()
        instances = converter.load_directory(dataset_info["path"])

    elif dataset_key == "security_code_gate_fixtures":
        converter = SecurityFixtureConverter()
        instances = converter.load_directory(dataset_info["path"])

    elif dataset_key in ("docile_kile", "docile_lir"):
        converter = DocILEConverter()
        task_type = dataset_info.get("task_type", "kile")
        split = dataset_kwargs.get("split")
        instances = converter.load_directory(
            dataset_info["path"],
            task_type=task_type,
            split=split,
        )

    elif dataset_key == "eltbench":
        converter = ELTBenchConverter(dataset_info["path"])
        instances = converter.load_all(max_tasks=max_instances)

    else:
        console.print(f" [{BRAND_ERROR}]✗[/{BRAND_ERROR}]")
        console.print(f"\n[{BRAND_ERROR}]Dataset '{dataset_key}' not yet supported with new converters.[/{BRAND_ERROR}]")
        return

    # Apply max_instances limit
    if max_instances:
        instances = instances[:max_instances]

    console.print(f" [{BRAND_SUCCESS}]✓[/{BRAND_SUCCESS}]")
    console.print(f"  [{BRAND_DIM}]Loaded[/{BRAND_DIM}] [{BRAND_PRIMARY}]{len(instances)}[/{BRAND_PRIMARY}] [{BRAND_DIM}]instances[/{BRAND_DIM}]")

    if not instances:
        console.print(f"\n[{BRAND_ERROR}]✗ No instances loaded.[/{BRAND_ERROR}]")
        return

    # Run benchmark - special handling for fixture tests
    console.print(f"\n  [{BRAND_ACCENT}]Running benchmark...[/{BRAND_ACCENT}]\n")

    if dataset_key == "security_code_gate_fixtures":
        # For fixture tests, run CodeShield directly (no LLM needed)
        console.print(f"  [{BRAND_DIM}]Running CODE GATE fixture validation (CodeShield)...[/{BRAND_DIM}]\n")
        result = run_fixture_benchmark(instances, verbose=verbose, log_dir=run_dir)
    else:
        # Get baseline kwargs from dataset (e.g., enable_output_gate for security_output_gate)
        extra_kwargs = dataset_info.get("baseline_kwargs", {})

        baseline_obj = get_baseline(
            baseline,
            provider=provider,
            model=model,
            enable_cache=enable_cache,
            verbose=verbose,
            log_dir=str(run_dir),  # Pass run directory for logging
            **extra_kwargs,  # Pass dataset-specific baseline kwargs
        )

        # Run using simple benchmark runner
        result = run_simple_benchmark(instances, baseline_obj, verbose=verbose, log_dir=run_dir)

    # Display results using simple format
    display_baseline = "fixture" if dataset_key == "security_code_gate_fixtures" else baseline
    display_simple_results(result, display_baseline, dataset_key)

    # Save detailed results to run directory
    results_path = run_dir / "results.json"
    results_data = {
        "instances": [
            {
                "instance_id": r.instance_id,
                "input": r.input,
                "output": r.output,
                "expected": r.expected,
                "success": r.success,
                "latency_ms": r.latency_ms,
                "error": r.error,
                "generation_time_ms": r.generation_time_ms,
                "execution_time_ms": r.execution_time_ms,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "generation_input_tokens": r.generation_input_tokens,
                "generation_output_tokens": r.generation_output_tokens,
                "execution_input_tokens": r.execution_input_tokens,
                "execution_output_tokens": r.execution_output_tokens,
                "match_type": r.match_type,
                "evaluation_score": r.evaluation_score,
                "evaluation_details": r.evaluation_details,
            }
            for r in result.results
        ]
    }

    with open(results_path, "w") as f:
        json.dump(results_data, f, indent=2)

    # Save detailed failures to separate file
    failures = [r for r in result.results if not r.success]
    if failures:
        failures_path = run_dir / "failures.json"
        failures_data = {
            "total_failures": len(failures),
            "failure_rate": len(failures) / len(result.results) if result.results else 0,
            "failures": [
                {
                    "instance_id": r.instance_id,
                    "input": r.input,
                    "output": r.output,
                    "expected": r.expected,
                    "error": r.error,
                    "match_type": r.match_type,
                    "evaluation_score": r.evaluation_score,
                    "evaluation_details": r.evaluation_details,
                    "latency_ms": r.latency_ms,
                    "generation_time_ms": r.generation_time_ms,
                    "execution_time_ms": r.execution_time_ms,
                    "tokens": {
                        "input": r.input_tokens,
                        "output": r.output_tokens,
                        "generation_input": r.generation_input_tokens,
                        "generation_output": r.generation_output_tokens,
                        "execution_input": r.execution_input_tokens,
                        "execution_output": r.execution_output_tokens,
                    }
                }
                for r in failures
            ]
        }
        with open(failures_path, "w") as f:
            json.dump(failures_data, f, indent=2)

    # Save summary to run directory
    summary_path = run_dir / "summary.json"
    summary_data = {
        "success_rate": result.success_rate,
        "duration_seconds": result.duration_seconds,
        "total_instances": len(result.results),
        "successful_instances": sum(1 for r in result.results if r.success),
        "failed_instances": sum(1 for r in result.results if not r.success),
    }

    # Add token breakdown for code_factory
    if baseline == "code_factory":
        total_gen_input = sum(r.generation_input_tokens or 0 for r in result.results)
        total_gen_output = sum(r.generation_output_tokens or 0 for r in result.results)
        total_exec_input = sum(r.execution_input_tokens or 0 for r in result.results)
        total_exec_output = sum(r.execution_output_tokens or 0 for r in result.results)

        summary_data["token_breakdown"] = {
            "compilation_input": total_gen_input,
            "compilation_output": total_gen_output,
            "compilation_total": total_gen_input + total_gen_output,
            "execution_input": total_exec_input,
            "execution_output": total_exec_output,
            "execution_total": total_exec_input + total_exec_output,
            "total": total_gen_input + total_gen_output + total_exec_input + total_exec_output,
        }

        compilations = sum(1 for r in result.results if r.generation_time_ms and r.generation_time_ms > 0)
        summary_data["compilations"] = compilations
        summary_data["cache_hits"] = len(result.results) - compilations

    with open(summary_path, "w") as f:
        json.dump(summary_data, f, indent=2)

    console.print(f"\n  [{BRAND_DIM}]Results saved to:[/{BRAND_DIM}]")
    console.print(f"    [{BRAND_PRIMARY}]{results_path}[/{BRAND_PRIMARY}]")
    console.print(f"    [{BRAND_PRIMARY}]{summary_path}[/{BRAND_PRIMARY}]")
    if failures:
        console.print(f"    [{BRAND_ERROR}]{failures_path} ({len(failures)} failures)[/{BRAND_ERROR}]")

    # Also save to results/ folder for consistency with other benchmarks
    import time
    results_folder = Path("results")
    results_folder.mkdir(exist_ok=True)
    timestamp = int(time.time())
    canonical_results_path = results_folder / f"{baseline}_{dataset_key}_{timestamp}.json"

    latencies = [r.latency_ms for r in result.results if r.latency_ms]
    p50_latency = sorted(latencies)[len(latencies) // 2] if latencies else 0
    p90_latency = sorted(latencies)[int(len(latencies) * 0.9)] if latencies else 0

    canonical_results = {
        "config": {
            "dataset": dataset_key,
            "baseline": baseline,
            "provider": provider,
            "max_instances": max_instances,
        },
        "summary": {
            "duration_seconds": result.duration_seconds,
            "overall_success_rate": result.success_rate,
            "total_instances": len(result.results),
            "successful_instances": sum(1 for r in result.results if r.success),
            "failed_instances": sum(1 for r in result.results if not r.success),
        },
        "metrics": {
            "p50_latency_ms": p50_latency,
            "p90_latency_ms": p90_latency,
        },
        "instances": [
            {
                "id": r.instance_id,
                "success": r.success,
                "latency_ms": r.latency_ms,
                "generation_time_ms": r.generation_time_ms,
                "execution_time_ms": r.execution_time_ms,
                "error": r.error,
            }
            for r in result.results
        ],
    }

    # Add token breakdown and latency breakdown for code_factory
    if baseline == "code_factory":
        canonical_results["token_breakdown"] = summary_data.get("token_breakdown", {})
        canonical_results["summary"]["compilations"] = summary_data.get("compilations", 0)
        canonical_results["summary"]["cache_hits"] = summary_data.get("cache_hits", 0)

        # Add latency breakdown (generation vs execution)
        gen_times = [r.generation_time_ms for r in result.results if r.generation_time_ms]
        exec_times = [r.execution_time_ms for r in result.results if r.execution_time_ms]

        if gen_times:
            canonical_results["metrics"]["p50_generation_ms"] = sorted(gen_times)[len(gen_times) // 2]
            canonical_results["metrics"]["p90_generation_ms"] = sorted(gen_times)[int(len(gen_times) * 0.9)]
            canonical_results["metrics"]["avg_generation_ms"] = sum(gen_times) / len(gen_times)

        if exec_times:
            canonical_results["metrics"]["p50_execution_ms"] = sorted(exec_times)[len(exec_times) // 2]
            canonical_results["metrics"]["p90_execution_ms"] = sorted(exec_times)[int(len(exec_times) * 0.9)]
            canonical_results["metrics"]["avg_execution_ms"] = sum(exec_times) / len(exec_times)

    with open(canonical_results_path, "w") as f:
        json.dump(canonical_results, f, indent=2)

    console.print(f"    [{BRAND_PRIMARY}]{canonical_results_path}[/{BRAND_PRIMARY}]")


def run_fixture_benchmark(
    instances: list[DatasetInstance],
    verbose: bool = False,
    log_dir: Path | None = None,
) -> SimpleBenchmarkResult:
    """Run CODE GATE fixture benchmark using CodeShield directly.

    For fixture tests, we validate pre-made vulnerable code directly with CodeShield
    instead of going through the full LLM-based code factory pipeline.

    Args:
        instances: List of DatasetInstance with activities.py code in input
        verbose: Print progress
        log_dir: Directory for logs

    Returns:
        SimpleBenchmarkResult with validation results
    """
    import time
    from compiled_ai.validation.code_shield import CodeShieldValidator

    validator = CodeShieldValidator(severity_threshold="warning")
    result = SimpleBenchmarkResult()
    result.start_time = time.time()

    for inst in instances:
        start = time.time()

        # The input IS the activities.py code for fixture tests
        code = inst.input
        expected = inst.expected_output or {}

        # Run CodeShield validation
        validation_result = validator.validate(code)

        # Determine if CODE GATE correctly blocked the vulnerable code
        expected_blocked = expected.get("blocked", True)
        actual_blocked = not validation_result.success

        # Success = expected blocking behavior matches actual
        success = expected_blocked == actual_blocked

        # Build output
        if validation_result.details.get("issues"):
            issues = validation_result.details["issues"]
            detected_cwes = [i.get("cwe_id") for i in issues if i.get("cwe_id")]
            detected_patterns = [i.get("pattern_id") for i in issues if i.get("pattern_id")]
            output = {
                "blocked": actual_blocked,
                "gate": "code" if actual_blocked else "none",
                "issues_found": len(issues),
                "cwe_ids": detected_cwes,
                "patterns": detected_patterns,
                "score": validation_result.score,
            }
        else:
            output = {
                "blocked": actual_blocked,
                "gate": "none",
                "issues_found": 0,
                "cwe_ids": [],
                "patterns": [],
                "score": validation_result.score,
            }

        latency = (time.time() - start) * 1000

        inst_result = InstanceResult(
            instance_id=inst.id,
            input=code[:500] + "..." if len(code) > 500 else code,
            output=str(output),
            expected=expected,
            success=success,
            latency_ms=latency,
            error=None if success else f"Expected blocked={expected_blocked}, got blocked={actual_blocked}",
            match_type="total_match" if success else "failure",
            evaluation_score=1.0 if success else 0.0,
            evaluation_details={
                "expected_blocked": expected_blocked,
                "actual_blocked": actual_blocked,
                "issues_found": output.get("issues_found", 0),
                "cwe_ids": output.get("cwe_ids", []),
            },
        )
        result.results.append(inst_result)

        if verbose:
            status = "BLOCKED" if actual_blocked else "PASSED"
            icon = "✓" if success else "✗"
            console.print(f"  {icon} {inst.id}: {status} (expected: {'blocked' if expected_blocked else 'passed'})")
            if output.get("cwe_ids"):
                console.print(f"    CWEs detected: {', '.join(output['cwe_ids'])}")

    result.end_time = time.time()
    return result


def display_simple_results(result: SimpleBenchmarkResult, baseline_name: str, dataset_key: str) -> None:
    """Display benchmark results from the new simple runner."""
    print_section("Results")
    console.print()

    # Summary panel
    success_rate = result.success_rate
    rate_color = BRAND_SUCCESS if success_rate >= 0.8 else BRAND_ACCENT if success_rate >= 0.5 else BRAND_ERROR

    # Calculate totals
    total_tokens = sum(r.input_tokens for r in result.results)
    compilations = sum(1 for r in result.results if r.generation_time_ms and r.generation_time_ms > 0)
    cache_hits = len(result.results) - compilations

    summary_text = Text()
    summary_text.append("Duration: ", style=BRAND_DIM)
    summary_text.append(f"{result.duration_seconds:.2f}s\n", style=BRAND_PRIMARY)
    summary_text.append("Instances: ", style=BRAND_DIM)
    summary_text.append(f"{len(result.results)}\n", style=BRAND_PRIMARY)
    summary_text.append("Success Rate: ", style=BRAND_DIM)
    summary_text.append(f"{success_rate:.1%}", style=f"bold {rate_color}")

    # Add Code Factory specific stats with token breakdown
    if baseline_name == "code_factory" and total_tokens > 0:
        summary_text.append(f"\nCompilations: ", style=BRAND_DIM)
        summary_text.append(f"{compilations}", style="yellow")
        summary_text.append(f" | Cache Hits: ", style=BRAND_DIM)
        summary_text.append(f"{cache_hits}", style="green")

        # Calculate token breakdown
        total_gen_input = sum(r.generation_input_tokens or 0 for r in result.results)
        total_gen_output = sum(r.generation_output_tokens or 0 for r in result.results)
        total_exec_input = sum(r.execution_input_tokens or 0 for r in result.results)
        total_exec_output = sum(r.execution_output_tokens or 0 for r in result.results)

        total_gen_tokens = total_gen_input + total_gen_output
        total_exec_tokens = total_exec_input + total_exec_output
        total_all_tokens = total_gen_tokens + total_exec_tokens

        summary_text.append(f"\n\nToken Breakdown:", style=f"bold {BRAND_PRIMARY}")
        summary_text.append(f"\n  Compilation: ", style=BRAND_DIM)
        summary_text.append(f"{total_gen_tokens:,}", style="yellow")
        summary_text.append(f" tokens ", style=BRAND_DIM)
        summary_text.append(f"(in: {total_gen_input:,}, out: {total_gen_output:,})", style=BRAND_DIM)
        summary_text.append(f"\n  Execution: ", style=BRAND_DIM)
        summary_text.append(f"{total_exec_tokens:,}", style="green")
        summary_text.append(f" tokens ", style=BRAND_DIM)
        summary_text.append(f"(in: {total_exec_input:,}, out: {total_exec_output:,})", style=BRAND_DIM)
        summary_text.append(f"\n  Total: ", style=BRAND_DIM)
        summary_text.append(f"{total_all_tokens:,}", style=BRAND_PRIMARY)
        summary_text.append(f" tokens", style=BRAND_DIM)

        # Amortization analysis
        if len(result.results) > 0:
            avg_tokens_per_instance = total_all_tokens / len(result.results)
            avg_exec_per_instance = total_exec_tokens / len(result.results)

            summary_text.append(f"\n\nAmortization:", style=f"bold {BRAND_PRIMARY}")
            summary_text.append(f"\n  Avg per instance: ", style=BRAND_DIM)
            summary_text.append(f"{avg_tokens_per_instance:,.0f}", style=BRAND_PRIMARY)
            summary_text.append(f" tokens", style=BRAND_DIM)

            # Show how cost decreases with more executions
            if compilations > 0 and avg_exec_per_instance < total_gen_tokens:
                # Break-even point: when compilation cost is amortized
                # Total cost with N instances: compilation + (execution × N)
                # At N=1: full compilation + 1 execution
                # At N=100: same compilation + 100 executions
                # Cost per instance decreases: (compilation + execution × N) / N

                summary_text.append(f"\n  Execution only: ", style=BRAND_DIM)
                summary_text.append(f"{avg_exec_per_instance:,.0f}", style="green")
                summary_text.append(f" tokens/instance", style=BRAND_DIM)

                # Show cost at different scales
                summary_text.append(f"\n  At 10 runs: ", style=BRAND_DIM)
                cost_10 = (total_gen_tokens + avg_exec_per_instance * 10) / 10
                summary_text.append(f"{cost_10:,.0f}", style=BRAND_ACCENT)
                summary_text.append(f" tokens/instance", style=BRAND_DIM)

                summary_text.append(f"\n  At 100 runs: ", style=BRAND_DIM)
                cost_100 = (total_gen_tokens + avg_exec_per_instance * 100) / 100
                summary_text.append(f"{cost_100:,.0f}", style=BRAND_ACCENT)
                summary_text.append(f" tokens/instance", style=BRAND_DIM)

    console.print(Panel(
        summary_text,
        title=f"[{BRAND_PRIMARY}]Summary[/{BRAND_PRIMARY}]",
        border_style=rate_color,
        box=box.ROUNDED,
    ))

    # Instance results table
    console.print()
    table = Table(
        title=f"[{BRAND_PRIMARY}]Instance Results[/{BRAND_PRIMARY}]",
        box=box.ROUNDED,
        border_style=BRAND_DIM,
        title_style=f"bold {BRAND_PRIMARY}",
    )
    table.add_column("Instance", style=BRAND_PRIMARY)
    table.add_column("Status", justify="center")
    table.add_column("Latency", justify="right", style=BRAND_DIM)

    # Add Code Factory specific columns
    is_code_factory = baseline_name == "code_factory"
    if is_code_factory:
        table.add_column("Gen (ms)", justify="right", style="yellow")
        table.add_column("Exec (ms)", justify="right", style="green")
        table.add_column("Tokens", justify="right", style=BRAND_DIM)

    # Show first 20 results
    for inst_result in result.results[:20]:
        status = f"[{BRAND_SUCCESS}]✓[/{BRAND_SUCCESS}]" if inst_result.success else f"[{BRAND_ERROR}]✗[/{BRAND_ERROR}]"

        row_data = [
            inst_result.instance_id[:40],
            status,
            f"{inst_result.latency_ms:.0f}ms",
        ]

        if is_code_factory:
            gen_ms = f"{inst_result.generation_time_ms:.0f}" if inst_result.generation_time_ms else "-"
            exec_ms = f"{inst_result.execution_time_ms:.0f}" if inst_result.execution_time_ms else "-"
            # Show token breakdown: compilation tokens / execution tokens
            gen_tokens = (inst_result.generation_input_tokens or 0) + (inst_result.generation_output_tokens or 0)
            exec_tokens = (inst_result.execution_input_tokens or 0) + (inst_result.execution_output_tokens or 0)
            if gen_tokens > 0:
                tokens = f"{gen_tokens:,} / {exec_tokens:,}"
            elif exec_tokens > 0:
                tokens = f"0 / {exec_tokens:,}"
            else:
                tokens = "-"
            row_data.extend([gen_ms, exec_ms, tokens])

        table.add_row(*row_data)

    if len(result.results) > 20:
        table.add_row("...", "...", "...", *(["-"] * 3 if is_code_factory else []))

    console.print(table)

    # Show failures
    failures = [r for r in result.results if not r.success]
    if failures:
        print_section("Failed Instances")
        for r in failures[:10]:
            console.print(f"\n  [{BRAND_ERROR}]✗[/{BRAND_ERROR}] [{BRAND_PRIMARY}]{r.instance_id}[/{BRAND_PRIMARY}]")
            if r.error:
                console.print(f"    [{BRAND_DIM}]Error:[/{BRAND_DIM}] [{BRAND_ERROR}]{r.error[:200]}[/{BRAND_ERROR}]")
            console.print(f"    [{BRAND_DIM}]Expected:[/{BRAND_DIM}] [{BRAND_SUCCESS}]{str(r.expected)[:100]}...[/{BRAND_SUCCESS}]")
            console.print(f"    [{BRAND_DIM}]Actual:[/{BRAND_DIM}]   [{BRAND_ACCENT}]{r.output[:100]}...[/{BRAND_ACCENT}]")

    console.print()


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
  python run_benchmark.py --dataset bfcl -b code_factory --categories simple --max-instances 5
  python run_benchmark.py --dataset agentbench --environments os db
  python run_benchmark.py --list                             # List datasets
  python run_benchmark.py --dataset bfcl --max-tasks 1 --max-instances 2  # Quick debug
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
        "--max-tasks",
        type=int,
        help="Max number of tasks to run (for quick debugging)",
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
        choices=["dev", "test", "train", "val"],
        default=None,
        help="Dataset split: dev/test for AgentBench, train/val for DocILE",
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
                max_tasks=args.max_tasks,
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
