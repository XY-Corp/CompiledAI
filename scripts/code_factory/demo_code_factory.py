"""Demo script showcasing Code Factory features."""

import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from compiled_ai.baselines import get_baseline, TaskInput
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load environment variables
load_dotenv()

console = Console()


async def demo():
    """Run a comprehensive demo of Code Factory features."""
    console.print(
        Panel.fit(
            "[bold cyan]Code Factory Demo[/bold cyan]\n\n"
            "This demo showcases:\n"
            "• Schema-aware code generation\n"
            "• Template activity inspiration\n"
            "• ASCII workflow visualization\n"
            "• Two-phase compilation/execution\n"
            "• Activity registry integration",
            border_style="cyan",
        )
    )

    # Initialize baseline with verbose logging
    baseline = get_baseline(
        "code_factory",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        verbose=True,
        enable_registry=True,
        auto_register=True,
    )

    console.print("\n[bold green]Phase 1: Compilation (Expensive)[/bold green]")
    console.print("First task triggers workflow generation with LLM calls\n")

    # First task - triggers compilation
    task1 = TaskInput(
        task_id="demo_001",
        prompt="Classify this support ticket: 'I cannot login to my account, keeps saying password is incorrect'",
        context={
            "categories": ["Billing", "Technical", "Account"],
        },
    )

    result1 = baseline.run(task1)

    console.print(
        Panel(
            f"[green]✓[/green] Task ID: {result1.task_id}\n"
            f"[green]✓[/green] Output: {result1.output[:100]}...\n"
            f"[green]✓[/green] Latency: {result1.latency_ms:.0f}ms\n"
            f"[green]✓[/green] Tokens: {result1.input_tokens + result1.output_tokens:,}",
            title="Task 1 Result",
            border_style="green",
        )
    )

    # Show compilation summary
    comp_summary = baseline.get_compilation_summary()
    console.print("\n[bold cyan]Compilation Summary:[/bold cyan]")
    console.print(f"  • Compilation tokens: {comp_summary['compilation_tokens']:,}")
    console.print(f"  • Compilation latency: {comp_summary['compilation_latency_ms']:.0f}ms")
    console.print(f"  • Workflow: {comp_summary['workflow_name']}")
    console.print(f"  • Activities: {comp_summary['activity_count']}")
    console.print(f"  • Regenerations: {comp_summary['regeneration_count']}")

    console.print("\n[bold green]Phase 2: Execution (Cheap)[/bold green]")
    console.print("Subsequent tasks reuse compiled workflow - no LLM calls!\n")

    # Execute 3 more tasks using compiled workflow
    tasks = [
        TaskInput(
            task_id=f"demo_{i:03d}",
            prompt=prompt,
            context={"categories": ["Billing", "Technical", "Account"]},
        )
        for i, prompt in enumerate(
            [
                "I was charged twice for my subscription this month",
                "The app crashes whenever I try to export data",
                "How do I reset my two-factor authentication?",
            ],
            start=2,
        )
    ]

    console.print("[bold]Executing 3 tasks in sequence...[/bold]\n")
    for task in tasks:
        result = baseline.run(task)
        status = "✓" if result.success else "✗"
        console.print(
            f"  {status} Task {result.task_id}: "
            f"Latency: {result.latency_ms:.0f}ms, "
            f"Tokens: {result.input_tokens + result.output_tokens}"
        )

    console.print(
        Panel.fit(
            "[bold green]Demo Complete![/bold green]\n\n"
            "[cyan]Key Observations:[/cyan]\n"
            "• First task: High latency (compilation)\n"
            "• Subsequent tasks: Low latency (execution only)\n"
            "• Token costs: High upfront, zero for execution\n"
            "• Workflow reuse: Same compiled code for all tasks\n\n"
            "[yellow]Value Proposition:[/yellow]\n"
            "Amortize expensive compilation over many cheap executions!",
            border_style="green",
        )
    )


if __name__ == "__main__":
    asyncio.run(demo())
