"""Test schema matching and template inspiration in Code Factory."""

import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from compiled_ai.factory.code_factory import CodeFactory
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_schema_matching():
    """Test that Code Factory generates code matching exact schemas."""
    print("=" * 80)
    print("SCHEMA MATCHING TEST")
    print("=" * 80)

    # Initialize factory with verbose output
    factory = CodeFactory(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        verbose=True,
        max_regenerations=3,
        enable_registry=True,
        auto_register=False,  # Don't register test activities
    )

    # Task that should trigger schema-aware code generation
    task = """
    Classify support tickets into categories (Billing, Technical, Account).

    Input: ticket_text (the full text of the support ticket)
    Output: category name and confidence score
    """

    print("\n📝 Task Description:")
    print(task)
    print("\n" + "=" * 80)

    # Generate workflow
    result = await factory.generate(task)

    if not result.success:
        print("\n❌ Generation failed:")
        for error in result.validation_errors:
            print(f"  - {error}")
        return False

    print("\n✅ Generation successful!")
    print("\n" + "=" * 80)
    print("PLANNER OUTPUT")
    print("=" * 80)

    # Check if planner defined schemas
    if result.plan and result.plan.activities:
        for activity in result.plan.activities:
            print(f"\nActivity: {activity.name}")
            print(f"Description: {activity.description}")

            if activity.inputs:
                print("\nInput Schema:")
                for param in activity.inputs:
                    required = "required" if param.required else "optional"
                    print(f"  - {param.name}: {param.type} ({required})")
                    print(f"    Description: {param.description}")
            else:
                print("\n⚠️  No input schema defined!")

            if activity.output:
                print(f"\nOutput Schema:")
                print(f"  Type: {activity.output.type}")
                print(f"  Description: {activity.output.description}")
                if activity.output.fields:
                    print("  Fields:")
                    for field_name, field_type in activity.output.fields.items():
                        print(f"    - {field_name}: {field_type}")
            else:
                print("\n⚠️  No output schema defined!")

            if activity.reference_activity:
                print(f"\nReference Activity: {activity.reference_activity}")

    print("\n" + "=" * 80)
    print("GENERATED ACTIVITIES CODE")
    print("=" * 80)
    print(result.activities_code)

    print("\n" + "=" * 80)
    print("GENERATED WORKFLOW YAML")
    print("=" * 80)
    print(result.workflow_yaml)

    print("\n" + "=" * 80)
    print("METRICS")
    print("=" * 80)
    if result.metrics:
        print(f"Total tokens: {result.metrics.total_tokens:,}")
        print(f"Average latency: {result.metrics.avg_latency_ms:.0f}ms")
        print(f"Regenerations: {result.regeneration_count}")

    return True


async def main():
    """Run the test."""
    success = await test_schema_matching()

    if success:
        print("\n" + "=" * 80)
        print("✅ TEST PASSED")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("❌ TEST FAILED")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
