"""Simple demo to showcase ASCII workflow visualization."""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from compiled_ai.baselines import TaskInput
from compiled_ai.baselines.code_factory import CodeFactoryBaseline
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def main():
    """Run a simple demo showing ASCII visualization."""
    print("=" * 80)
    print("CODE FACTORY - ASCII WORKFLOW VISUALIZATION DEMO")
    print("=" * 80)
    print()

    # Initialize baseline with verbose logging
    print("Initializing Code Factory baseline with verbose mode...\n")
    baseline = CodeFactoryBaseline(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        verbose=True,  # This enables ASCII visualization
        enable_registry=True,
        auto_register=True,
    )

    # Create a classification task
    task = TaskInput(
        task_id="demo_001",
        prompt="Classify support tickets into categories: Billing, Technical, or Account",
        context={
            "ticket_text": "I was charged twice for my subscription this month",
        },
    )

    print("Running task: Classify support tickets")
    print("This will trigger compilation and show the ASCII workflow diagram...\n")

    # Run the task - this will show ASCII diagram during compilation
    result = baseline.run(task)

    print("\n" + "=" * 80)
    print("RESULT")
    print("=" * 80)
    print(f"Success: {result.success}")
    print(f"Task ID: {result.task_id}")
    print(f"Latency: {result.latency_ms:.0f}ms")
    print(f"Tokens: {result.input_tokens + result.output_tokens:,}")
    print()

    # Show compilation summary
    summary = baseline.get_compilation_summary()
    if summary.get("compiled"):
        print("=" * 80)
        print("COMPILATION SUMMARY")
        print("=" * 80)
        print(f"Workflow: {summary['workflow_name']}")
        print(f"Activities: {summary['activity_count']}")
        print(f"Compilation Tokens: {summary['compilation_tokens']:,}")
        print(f"Compilation Latency: {summary['compilation_latency_ms']:.0f}ms")
        print(f"Regenerations: {summary['regeneration_count']}")
        print()


if __name__ == "__main__":
    main()
