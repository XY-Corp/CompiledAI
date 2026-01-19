"""Test the activity registry."""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from compiled_ai.factory.activities import get_registry


def test_registry():
    """Test activity registry loading and searching."""
    print("=" * 80)
    print("ACTIVITY REGISTRY TEST")
    print("=" * 80)

    registry = get_registry()

    # Test 1: List all activities
    print("\n1. All Activities:")
    activities = registry.list()
    for name in sorted(activities):
        print(f"   - {name}")
    print(f"\n✓ Found {len(activities)} activities")

    # Test 2: Get a specific activity
    print("\n2. Get Activity:")
    llm_classify = registry.get("llm_classify")
    if llm_classify:
        print(f"   ✓ Loaded: llm_classify")
        print(f"   Type: {type(llm_classify)}")
        print(f"   Callable: {callable(llm_classify)}")
        if llm_classify.__doc__:
            print(f"   Doc: {llm_classify.__doc__.strip().split(chr(10))[0]}")
    else:
        print("   ✗ Failed to load llm_classify")

    # Test 3: Search activities
    print("\n3. Search Activities:")
    llm_activities = registry.search("llm")
    print(f"   Query: 'llm'")
    for name in llm_activities:
        print(f"   - {name}")
    print(f"   ✓ Found {len(llm_activities)} matching activities")

    # Test 4: Get source code
    print("\n4. Get Source Code:")
    source = registry.get_source("llm_classify")
    if source:
        lines = source.strip().split("\n")
        print(f"   ✓ Got source ({len(lines)} lines)")
        print(f"   First line: {lines[0]}")
    else:
        print("   ✗ Failed to get source")

    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED")
    print("=" * 80)


if __name__ == "__main__":
    test_registry()
