"""Simple example demonstrating Activity Template Registry usage.

This script shows how to:
1. Initialize CodeFactory with registry enabled
2. Generate workflows that leverage existing templates
3. View the registry contents
4. Search for specific templates
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

from compiled_ai.factory.code_factory import CodeFactory, TemplateRegistry, TemplateCategory


async def main():
    """Demonstrate registry usage."""

    print("\n" + "=" * 80)
    print("ACTIVITY TEMPLATE REGISTRY - SIMPLE EXAMPLE")
    print("=" * 80)

    # 1. Initialize factory with registry
    print("\n1️⃣  Initializing CodeFactory with registry enabled...")
    factory = CodeFactory(
        provider="anthropic",
        verbose=True,
        enable_registry=True,
        auto_register=True,
    )

    print(f"   ✓ Registry loaded with {len(factory.registry.list_all())} built-in templates")

    # 2. View available templates
    print("\n2️⃣  Available template categories:")
    for category in TemplateCategory:
        templates = factory.registry.list_all(category=category)
        if templates:
            print(f"   • {category.value}: {len(templates)} templates")
            for t in templates:
                print(f"     - {t.name}")

    # 3. Search for templates
    print("\n3️⃣  Searching for templates...")
    print("\n   🔍 Search: 'classify text into categories'")
    results = factory.registry.search("classify text into categories", limit=3)
    for i, r in enumerate(results, 1):
        print(f"   {i}. {r.template.name} (score: {r.score:.2f})")
        print(f"      {r.template.description[:60]}...")

    # 4. Generate a workflow
    print("\n4️⃣  Generating a workflow...")
    print("   Task: Classify customer feedback and extract sentiment\n")

    result = await factory.generate(
        "Classify customer feedback into categories (bug, feature request, praise) "
        "and extract sentiment score"
    )

    if result.success:
        print(f"\n   ✅ Success!")
        print(f"   • Workflow: {result.plan.name}")
        print(f"   • Activities: {[a.name for a in result.plan.activities]}")
        print(f"   • Pattern: {result.plan.execution_pattern}")
        print(f"   • Regenerations: {result.regeneration_count}")
        print(f"   • Total tokens: {result.metrics.total_tokens if result.metrics else 0}")

        # Show the YAML
        print("\n   📄 Generated YAML:")
        print("   " + "-" * 76)
        for line in result.workflow_yaml.split("\n")[:20]:
            print(f"   {line}")
        if result.workflow_yaml.count("\n") > 20:
            print("   ...")
        print("   " + "-" * 76)

    else:
        print(f"\n   ❌ Failed: {result.validation_errors}")

    # 5. Check registry growth
    print(f"\n5️⃣  Registry now has {len(factory.registry.list_all())} templates")

    print("\n" + "=" * 80)
    print("✨ Example complete!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
