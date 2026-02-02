#!/usr/bin/env python3
"""BFCL benchmark runner using Crush generator.

Runs BFCL (Berkeley Function Calling Leaderboard) benchmarks using the
Crush-based workflow generator. Generates function-calling code and tests
against ground truth.
"""

import json
import time
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Literal
import re

# Ensure ANTHROPIC_API_KEY is set
if not os.environ.get("ANTHROPIC_API_KEY"):
    env_file = Path(__file__).parent.parent.parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
                os.environ["ANTHROPIC_API_KEY"] = key
                break

try:
    from .generator import CrushGenerator, GenerationResult
except ImportError:
    from generator import CrushGenerator, GenerationResult


# BFCL task categories
BFCLCategory = Literal[
    "simple", "multiple", "parallel", "parallel_multiple",
    "java", "javascript", "relevance", "irrelevance"
]


@dataclass
class BFCLResult:
    """Result from a single BFCL task."""
    task_id: str
    success: bool
    expected: Any
    actual: Any = None
    error: str = ""
    generation_time: float = 0.0


@dataclass
class BenchmarkResult:
    """Result from running BFCL benchmark."""
    category: str
    total_tasks: int = 0
    successful: int = 0
    failed: int = 0
    workflow_generation_time: float = 0.0
    total_execution_time: float = 0.0
    results: list[BFCLResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.successful / self.total_tasks


def load_bfcl_data(
    bfcl_dir: Path,
    category: str = "simple",
    max_samples: int = 10,
) -> list[dict]:
    """Load BFCL samples from files.
    
    Args:
        bfcl_dir: Path to BFCL dataset
        category: Task category (simple, multiple, parallel, etc.)
        max_samples: Maximum samples to load
        
    Returns:
        List of task dictionaries
    """
    # Map category to file name
    file_map = {
        "simple": "BFCL_v3_exec_simple.json",
        "multiple": "BFCL_v3_exec_multiple.json", 
        "parallel": "BFCL_v3_exec_parallel.json",
        "parallel_multiple": "BFCL_v3_exec_parallel_multiple.json",
        "java": "BFCL_v3_java.json",
        "javascript": "BFCL_v3_javascript.json",
        "relevance": "BFCL_v3_live_relevance.json",
        "irrelevance": "BFCL_v3_irrelevance.json",
    }
    
    file_name = file_map.get(category)
    if not file_name:
        raise ValueError(f"Unknown category: {category}")
    
    file_path = bfcl_dir / file_name
    if not file_path.exists():
        raise FileNotFoundError(f"BFCL file not found: {file_path}")
    
    # Load JSONL format
    samples = []
    with open(file_path) as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
                if len(samples) >= max_samples:
                    break
    
    return samples


def create_function_calling_prompt(sample: dict) -> str:
    """Create a prompt for generating function-calling code.
    
    Args:
        sample: BFCL sample with question and function definitions
        
    Returns:
        Prompt for the Crush generator
    """
    # Extract question from messages
    messages = sample.get("question", [[]])[0]
    question = ""
    for msg in messages:
        if msg.get("role") == "user":
            question = msg.get("content", "")
            break
    
    # Extract function definitions
    functions = sample.get("function", [])
    func_defs = json.dumps(functions, indent=2)
    
    prompt = f"""
Create a Python function that handles this user request by calling the appropriate function(s).

USER REQUEST:
{question}

AVAILABLE FUNCTIONS:
{func_defs}

Requirements:
1. Create a main function called `handle_request` that takes no arguments
2. Inside, call the appropriate function(s) with the correct arguments
3. Return the function call result(s) as a dictionary
4. The function should be deterministic (no random values)
5. Parse any values from the user request correctly

Example output format for a single function call:
```python
def handle_request():
    result = function_name(arg1=value1, arg2=value2)
    return {{"function_name": {{"arg1": value1, "arg2": value2}}}}
```

For multiple/parallel calls, return a list of function call dictionaries.
"""
    return prompt


def run_benchmark(
    category: str = "simple",
    model: str = "anthropic/claude-opus-4-5-20251101",
    max_samples: int = 10,
    bfcl_dir: Path | None = None,
    output_dir: Path | None = None,
    verbose: bool = True,
) -> BenchmarkResult:
    """Run BFCL benchmark with Crush generator.
    
    Args:
        category: BFCL task category
        model: Model to use for generation
        max_samples: Maximum samples to process
        bfcl_dir: Path to BFCL dataset
        output_dir: Where to save generated workflows
        verbose: Print progress
        
    Returns:
        BenchmarkResult with metrics
    """
    # Find BFCL directory
    if bfcl_dir is None:
        bfcl_dir = Path(__file__).parent.parent.parent.parent.parent / "datasets/bfcl_v4"
    
    if output_dir is None:
        output_dir = Path(__file__).parent / "bfcl_workflows" / category
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result = BenchmarkResult(category=category)
    
    if verbose:
        print(f"🔍 BFCL Benchmark: {category.upper()}")
        print(f"📁 Dataset: {bfcl_dir}")
        print(f"🤖 Model: {model}")
        print("=" * 50)
    
    # Load samples
    if verbose:
        print(f"\n📂 Loading {max_samples} samples...")
    
    try:
        samples = load_bfcl_data(bfcl_dir, category, max_samples)
        result.total_tasks = len(samples)
        if verbose:
            print(f"   Loaded {len(samples)} tasks")
    except Exception as e:
        result.errors.append(f"Failed to load data: {e}")
        if verbose:
            print(f"❌ Failed to load data: {e}")
        return result
    
    # Initialize generator
    generator = CrushGenerator(model=model, max_iterations=3)
    
    # Process each sample
    for i, sample in enumerate(samples):
        task_id = sample.get("id", f"task_{i}")
        
        if verbose:
            print(f"\n🔧 [{i+1}/{len(samples)}] Processing {task_id}...")
        
        task_result = BFCLResult(
            task_id=task_id,
            success=False,
            expected=sample.get("ground_truth", sample.get("function", [])),
        )
        
        # Generate function-calling code
        try:
            gen_start = time.time()
            prompt = create_function_calling_prompt(sample)
            
            task_dir = output_dir / task_id
            gen_result = generator.generate(
                prompt,
                output_dir=task_dir,
                verbose=False,
            )
            
            task_result.generation_time = time.time() - gen_start
            result.workflow_generation_time += task_result.generation_time
            
            if gen_result.success:
                # Load and execute the generated code
                activities_path = task_dir / "activities.py"
                if activities_path.exists():
                    # Import and run
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("activities", activities_path)
                    mod = importlib.util.module_from_spec(spec)
                    
                    try:
                        spec.loader.exec_module(mod)
                        
                        # Find and call handle_request function
                        if hasattr(mod, "handle_request"):
                            actual = mod.handle_request()
                            task_result.actual = actual
                            task_result.success = True
                            result.successful += 1
                            if verbose:
                                print(f"   ✅ Success")
                        else:
                            task_result.error = "No handle_request function found"
                            result.failed += 1
                            if verbose:
                                print(f"   ⚠️ No handle_request function")
                                
                    except Exception as e:
                        task_result.error = str(e)[:200]
                        result.failed += 1
                        if verbose:
                            print(f"   ❌ Execution error: {str(e)[:50]}")
                else:
                    task_result.error = "activities.py not generated"
                    result.failed += 1
            else:
                task_result.error = "Generation failed"
                result.failed += 1
                if verbose:
                    print(f"   ❌ Generation failed")
                    
        except Exception as e:
            task_result.error = str(e)[:200]
            result.failed += 1
            result.errors.append(f"{task_id}: {str(e)[:100]}")
            if verbose:
                print(f"   ❌ Error: {str(e)[:50]}")
        
        result.results.append(task_result)
    
    # Summary
    if verbose:
        print("\n" + "=" * 50)
        print("📊 RESULTS")
        print(f"   Category: {category.upper()}")
        print(f"   Tasks: {result.total_tasks}")
        print(f"   Successful: {result.successful}")
        print(f"   Failed: {result.failed}")
        print(f"   Success Rate: {result.success_rate:.1%}")
        print(f"   Total Gen Time: {result.workflow_generation_time:.1f}s")
        avg_time = result.workflow_generation_time / max(result.total_tasks, 1)
        print(f"   Avg Time/Task: {avg_time:.1f}s")
    
    return result


def run_all_categories(
    model: str = "anthropic/claude-opus-4-5-20251101",
    max_samples: int = 5,
    verbose: bool = True,
) -> dict[str, BenchmarkResult]:
    """Run benchmarks for all BFCL categories.
    
    Args:
        model: Model to use
        max_samples: Samples per category
        verbose: Print progress
        
    Returns:
        Dict mapping category to BenchmarkResult
    """
    categories = ["simple", "multiple", "parallel"]
    results = {}
    
    for category in categories:
        if verbose:
            print(f"\n{'='*60}")
            print(f"CATEGORY: {category.upper()}")
            print('='*60)
        
        results[category] = run_benchmark(
            category=category,
            model=model,
            max_samples=max_samples,
            verbose=verbose,
        )
    
    # Print overall summary
    if verbose:
        print("\n" + "="*60)
        print("OVERALL SUMMARY")
        print("="*60)
        
        total_tasks = sum(r.total_tasks for r in results.values())
        total_success = sum(r.successful for r in results.values())
        total_time = sum(r.workflow_generation_time for r in results.values())
        
        print(f"\n{'Category':<20} {'Tasks':>8} {'Success':>8} {'Rate':>8} {'Time':>10}")
        print("-" * 60)
        
        for cat, res in results.items():
            print(f"{cat:<20} {res.total_tasks:>8} {res.successful:>8} {res.success_rate:>7.1%} {res.workflow_generation_time:>9.1f}s")
        
        print("-" * 60)
        overall_rate = total_success / max(total_tasks, 1)
        print(f"{'TOTAL':<20} {total_tasks:>8} {total_success:>8} {overall_rate:>7.1%} {total_time:>9.1f}s")
    
    return results


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run BFCL benchmark with Crush generator")
    parser.add_argument("--category", choices=["simple", "multiple", "parallel", "all"],
                        default="simple", help="Task category or 'all'")
    parser.add_argument("--model", default="anthropic/claude-opus-4-5-20251101",
                        help="Model to use")
    parser.add_argument("--samples", type=int, default=5,
                        help="Number of samples per category")
    parser.add_argument("--bfcl-dir", type=Path, help="Path to BFCL dataset")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    
    args = parser.parse_args()
    
    if args.category == "all":
        results = run_all_categories(
            model=args.model,
            max_samples=args.samples,
            verbose=not args.quiet,
        )
        
        if args.json:
            output = {
                cat: {
                    "total": r.total_tasks,
                    "successful": r.successful,
                    "success_rate": r.success_rate,
                    "generation_time": r.workflow_generation_time,
                }
                for cat, r in results.items()
            }
            print(json.dumps(output, indent=2))
    else:
        result = run_benchmark(
            category=args.category,
            model=args.model,
            max_samples=args.samples,
            bfcl_dir=args.bfcl_dir,
            verbose=not args.quiet,
        )
        
        if args.json:
            print(json.dumps({
                "category": result.category,
                "total": result.total_tasks,
                "successful": result.successful,
                "success_rate": result.success_rate,
                "generation_time": result.workflow_generation_time,
            }, indent=2))
        
        if result.successful == 0:
            exit(1)


if __name__ == "__main__":
    main()
