#!/usr/bin/env python3
"""Test script for the Crush-based workflow generator."""

import sys
import tempfile
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from runner import CrushRunner
from generator import CrushGenerator


def test_runner():
    """Test the CrushRunner directly."""
    print("=" * 60)
    print("Testing CrushRunner")
    print("=" * 60)
    
    runner = CrushRunner(model="gemini/gemini-2.5-flash")
    
    # Simple test
    with tempfile.TemporaryDirectory() as tmpdir:
        runner.working_dir = Path(tmpdir)
        
        result = runner.run(
            "Create a simple Python file called hello.py that prints 'Hello, World!'",
            verbose=True,
        )
        
        print(f"\nSuccess: {result.success}")
        print(f"Return code: {result.return_code}")
        print(f"Files created: {result.files_created}")
        print(f"Files modified: {result.files_modified}")
        
        # Check if file was created
        hello_path = Path(tmpdir) / "hello.py"
        if hello_path.exists():
            print(f"\nGenerated code:\n{hello_path.read_text()}")
        else:
            print("\n⚠️ hello.py was not created")
        
        return result.success


def test_generator():
    """Test the full CrushGenerator pipeline."""
    print("\n" + "=" * 60)
    print("Testing CrushGenerator")
    print("=" * 60)
    
    generator = CrushGenerator(
        model="gemini/gemini-2.5-flash",  # Use Gemini for speed
        max_iterations=3,
        timeout_per_step=90,
    )
    
    task = """
    Create a workflow that:
    1. Takes a list of email addresses
    2. Validates each email format using regex
    3. Returns a dict with 'valid' and 'invalid' lists
    """
    
    with tempfile.TemporaryDirectory() as tmpdir:
        result = generator.generate(
            task,
            output_dir=Path(tmpdir),
            verbose=True,
        )
        
        print("\n" + "-" * 40)
        print("Generation Result:")
        print(f"  Success: {result.success}")
        print(f"  Iterations: {result.iterations}")
        print(f"  Time: {result.total_time_seconds:.1f}s")
        
        if result.errors:
            print(f"  Errors:")
            for e in result.errors[-3:]:
                print(f"    - {e[:80]}...")
        
        if result.workflow_yaml:
            print(f"\n📋 Workflow YAML ({len(result.workflow_yaml)} chars):")
            print(result.workflow_yaml[:500])
        
        if result.activities_code:
            print(f"\n🐍 Activities ({len(result.activities_code)} chars):")
            print(result.activities_code[:500])
        
        return result.success


if __name__ == "__main__":
    print("🧪 Crush Generator Test Suite\n")
    
    # Test 1: Runner
    runner_ok = test_runner()
    
    # Test 2: Full generator
    generator_ok = test_generator()
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Runner: {'✅ PASS' if runner_ok else '❌ FAIL'}")
    print(f"  Generator: {'✅ PASS' if generator_ok else '❌ FAIL'}")
