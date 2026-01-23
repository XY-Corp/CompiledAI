"""Debug a single task to see generated workflow."""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from compiled_ai.baselines.base import TaskInput
from compiled_ai.baselines.code_factory import CodeFactoryBaseline


def main():
    """Run a single failing task with verbose output."""

    # Create baseline with verbose mode
    baseline = CodeFactoryBaseline(
        provider="anthropic",
        verbose=True,
        enable_registry=True,
    )

    # Test json_transform task (currently failing)
    task = TaskInput(
        task_id="json_transform_01_test",
        prompt="""Transform this JSON from the source format to the target format.

Source:
{"first_name": "John", "last_name": "Doe", "email_address": "john@example.com"}

Target Schema:
{"fullName": "string", "email": "string"}

Return only the transformed JSON.""",
        context={
            "source_json": {"first_name": "John", "last_name": "Doe", "email_address": "john@example.com"},
            "target_schema": {"fullName": "string", "email": "string"}
        },
    )

    print("=" * 80)
    print("Running json_transform task...")
    print("=" * 80)

    result = baseline.run(task)

    print("\n" + "=" * 80)
    print("RESULT:")
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"Error: {result.error}")
    print("=" * 80)

    # Show generated code for debugging
    if hasattr(baseline, '_last_factory_result') and baseline._last_factory_result:
        print("\n" + "=" * 80)
        print("GENERATED ACTIVITIES CODE:")
        print("=" * 80)
        print(baseline._last_factory_result.activities_code)


if __name__ == "__main__":
    main()
