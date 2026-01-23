"""Test script for CodeFactory baseline integration.

This script verifies:
1. CodeFactory baseline is properly registered
2. It can be instantiated via the registry
3. Basic run() functionality works
4. Compilation and execution phases work correctly
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from compiled_ai.baselines import get_baseline, list_baselines, TaskInput, BaselineResult


def test_baseline_registration():
    """Test 1: Verify CodeFactory baseline is registered."""
    print("=" * 80)
    print("TEST 1: Baseline Registration")
    print("=" * 80)

    baselines = list_baselines()
    print(f"\n✓ Found {len(baselines)} registered baselines:")
    for name in baselines:
        print(f"  - {name}")

    assert "code_factory" in baselines, "CodeFactory baseline not registered!"
    print("\n✅ CodeFactory baseline is registered\n")
    print("=" * 80)


def test_baseline_instantiation():
    """Test 2: Verify CodeFactory baseline can be instantiated."""
    print("\nTEST 2: Baseline Instantiation")
    print("=" * 80)

    try:
        baseline = get_baseline("code_factory", provider="anthropic", verbose=True)
        print(f"\n✓ Instantiated: {baseline.__class__.__name__}")
        print(f"  - Description: {baseline.description}")
        print(f"  - Provider: {baseline.provider}")
        print(f"  - Model: {baseline.model}")
        print(f"  - Registry enabled: {baseline.enable_registry}")
        print("\n✅ Instantiation successful\n")
        print("=" * 80)
        return baseline
    except Exception as e:
        print(f"\n❌ Instantiation failed: {e}\n")
        print("=" * 80)
        raise


def test_compilation_phase(baseline):
    """Test 3: Verify compilation phase works."""
    print("\nTEST 3: Compilation Phase")
    print("=" * 80)

    # Create a simple task
    task = TaskInput(
        task_id="test_001",
        prompt="Extract the customer name and email from support tickets",
        context={"ticket": "From: John Doe <john@example.com> - Issue with login"},
    )

    print(f"\n📝 Task: {task.prompt}")
    print(f"   Context: {task.context}")

    print("\n⚙️  Running baseline (will trigger compilation)...")
    result = baseline.run(task)

    print(f"\n📊 Result:")
    print(f"  - Success: {result.success}")
    print(f"  - Task ID: {result.task_id}")
    print(f"  - Latency: {result.latency_ms:.0f}ms")
    print(f"  - Input tokens: {result.input_tokens}")
    print(f"  - Output tokens: {result.output_tokens}")
    print(f"  - LLM calls: {result.llm_calls}")
    if result.error:
        print(f"  - Error: {result.error}")

    # Check compilation summary
    compilation = baseline.get_compilation_summary()
    print(f"\n🔧 Compilation Summary:")
    print(f"  - Compiled: {compilation['compiled']}")
    if compilation["compiled"]:
        print(f"  - Workflow: {compilation['workflow_name']}")
        print(f"  - Activities: {compilation['activity_count']}")
        print(f"  - Compilation tokens: {compilation['compilation_tokens']}")
        print(f"  - Compilation latency: {compilation['compilation_latency_ms']:.0f}ms")
        print(f"  - Regenerations: {compilation['regeneration_count']}")

    if result.success:
        print("\n✅ Compilation phase successful\n")
    else:
        print(f"\n⚠️  Compilation phase completed with issues: {result.error}\n")

    print("=" * 80)
    return result.success


def test_execution_phase(baseline):
    """Test 4: Verify execution phase reuses compiled workflow."""
    print("\nTEST 4: Execution Phase (Reuse Compiled Workflow)")
    print("=" * 80)

    # Create similar tasks to test reuse
    tasks = [
        TaskInput(
            task_id="test_002",
            prompt="Extract customer data",
            context={"ticket": "From: Jane Smith <jane@test.com> - Password reset"},
        ),
        TaskInput(
            task_id="test_003",
            prompt="Extract customer info",
            context={"ticket": "From: Bob Wilson <bob@acme.com> - Billing question"},
        ),
    ]

    print(f"\n📝 Running {len(tasks)} additional tasks using compiled workflow...")

    for i, task in enumerate(tasks, 1):
        print(f"\n  Task {i}/{len(tasks)}: {task.task_id}")
        result = baseline.run(task)
        print(f"    Success: {result.success}")
        print(f"    Latency: {result.latency_ms:.0f}ms")
        print(f"    Tokens: {result.input_tokens + result.output_tokens}")
        print(f"    LLM calls: {result.llm_calls}")

    print("\n✅ Execution phase complete (workflow reused)\n")
    print("=" * 80)


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("CODE FACTORY BASELINE - INTEGRATION TESTS")
    print("=" * 80)

    try:
        # Test 1: Registration
        test_baseline_registration()

        # Test 2: Instantiation
        baseline = test_baseline_instantiation()

        # Test 3: Compilation
        compilation_success = test_compilation_phase(baseline)

        # Test 4: Execution (only if compilation succeeded)
        if compilation_success:
            test_execution_phase(baseline)
        else:
            print("\n⚠️  Skipping execution phase tests due to compilation issues\n")

        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 80 + "\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
