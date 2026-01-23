"""Test script for the Activity Template Registry system.

This script demonstrates:
1. Template registry initialization with built-in templates
2. Template search functionality
3. Code Factory integration with registry
4. Auto-registration of successful activities
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

from compiled_ai.factory.code_factory import CodeFactory
from compiled_ai.factory.code_factory.template_registry import TemplateRegistry, TemplateCategory


async def test_builtin_templates():
    """Test 1: Verify built-in templates are loaded."""
    print("=" * 80)
    print("TEST 1: Built-in Templates")
    print("=" * 80)

    registry = TemplateRegistry()
    templates = registry.list_all()

    print(f"\n✓ Loaded {len(templates)} built-in templates:")
    for t in templates:
        print(f"  - {t.name} ({t.category.value}): {t.description[:60]}...")

    print("\n" + "=" * 80)


async def test_template_search():
    """Test 2: Test template search functionality."""
    print("\nTEST 2: Template Search")
    print("=" * 80)

    registry = TemplateRegistry()

    # Test 1: Search for LLM-related activities
    print("\n🔍 Search: 'extract data from text'")
    results = registry.search("extract data from text", limit=3)
    print(f"Found {len(results)} matches:")
    for r in results:
        print(f"  - {r.template.name} (score: {r.score:.2f}, match: {r.match_type})")

    # Test 2: Search for HTTP activities
    print("\n🔍 Search: 'make http request'")
    results = registry.search("make http request", limit=3)
    print(f"Found {len(results)} matches:")
    for r in results:
        print(f"  - {r.template.name} (score: {r.score:.2f}, match: {r.match_type})")

    # Test 3: Search with category filter
    print("\n🔍 Search: 'transform' with category filter 'data'")
    results = registry.search("transform", category=TemplateCategory.DATA, limit=3)
    print(f"Found {len(results)} matches:")
    for r in results:
        print(f"  - {r.template.name} (score: {r.score:.2f}, match: {r.match_type})")

    print("\n" + "=" * 80)


async def test_factory_with_registry():
    """Test 3: Test Code Factory with registry integration."""
    print("\nTEST 3: Code Factory with Registry")
    print("=" * 80)

    # Initialize factory with registry enabled
    factory = CodeFactory(
        provider="anthropic",
        verbose=True,
        enable_registry=True,
        auto_register=True,
    )

    print("\n✓ CodeFactory initialized with registry enabled")
    print(f"  - Registry templates: {len(factory.registry.list_all())}")
    print(f"  - Auto-registration: {'enabled' if factory.registrar else 'disabled'}")

    # Generate a simple workflow that uses LLM extraction
    task = "Extract customer name and email from support tickets"

    print(f"\n📝 Task: {task}")
    print("\n⚙️ Generating workflow...")

    result = await factory.generate(task)

    if result.success:
        print("\n✅ Generation successful!")
        print(f"  - Workflow: {result.plan.name}")
        print(f"  - Activities: {[a.name for a in result.plan.activities]}")
        print(f"  - Regenerations: {result.regeneration_count}")
        print(f"  - Total tokens: {result.metrics.total_tokens if result.metrics else 0}")

        # Check if activities were registered
        print(f"\n  - Registry now has: {len(factory.registry.list_all())} templates")

        # Show generated workflow YAML (first 500 chars)
        print("\n📄 Generated YAML (preview):")
        print("-" * 80)
        print(result.workflow_yaml[:500])
        if len(result.workflow_yaml) > 500:
            print("...")
        print("-" * 80)

    else:
        print("\n❌ Generation failed!")
        print(f"  - Errors: {result.validation_errors}")

    print("\n" + "=" * 80)
    return result


async def test_registry_growth():
    """Test 4: Test that registry grows with successful generations."""
    print("\nTEST 4: Registry Growth")
    print("=" * 80)

    factory = CodeFactory(
        provider="anthropic",
        verbose=False,  # Reduce output
        enable_registry=True,
        auto_register=True,
    )

    initial_count = len(factory.registry.list_all())
    print(f"\n📊 Initial templates: {initial_count}")

    # Generate a workflow
    print("\n⚙️ Generating workflow...")
    result = await factory.generate(
        "Validate customer data and send notification email"
    )

    final_count = len(factory.registry.list_all())
    print(f"\n📊 Final templates: {final_count}")
    print(f"  - New templates added: {final_count - initial_count}")

    if result.success:
        print("\n✓ Workflow generated successfully")

        # Show which activities were registered
        new_templates = factory.registry.list_all()[initial_count:]
        if new_templates:
            print("\n📝 New templates registered:")
            for t in new_templates:
                print(f"  - {t.name} ({t.category.value})")
                print(f"    Tags: {', '.join(t.tags[:5])}")
                print(f"    Description: {t.description[:60]}...")
    else:
        print("\n✗ Workflow generation failed")

    print("\n" + "=" * 80)


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("ACTIVITY TEMPLATE REGISTRY - TEST SUITE")
    print("=" * 80)

    try:
        # Test 1: Built-in templates
        await test_builtin_templates()

        # Test 2: Template search
        await test_template_search()

        # Test 3: Factory with registry
        await test_factory_with_registry()

        # Test 4: Registry growth
        await test_registry_growth()

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
    asyncio.run(main())
