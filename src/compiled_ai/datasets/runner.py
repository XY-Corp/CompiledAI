"""Simple benchmark runner using the generic DatasetInstance format.

Supports two evaluation modes:
1. Exact match: Uses DatasetInstance.matches() for exact comparison
2. LLM evaluation: Uses LLMEvaluator for semantic comparison with match types:
   - total_match: Format AND content match (score=1.0)
   - content_match: Content correct, format differs (score=0.8)
   - format_match: Format correct, content wrong (score=0.3)
   - failure: Neither matches (score=0.0)
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from rich.console import Console
from rich.table import Table
from rich import box

from .base import DatasetInstance
from ..baselines.base import BaseBaseline, BaselineResult, TaskInput, get_baseline
from ..evaluation import LLMEvaluator, EvaluationResult

console = Console()


EvaluationMode = Literal["exact", "llm"]


@dataclass
class InstanceResult:
    """Result for a single instance."""

    instance_id: str
    input: str
    output: str
    expected: Any  # Can be single value or list
    success: bool
    latency_ms: float = 0.0
    error: str | None = None

    # Code Factory metrics
    generation_time_ms: float | None = None
    execution_time_ms: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0

    # Token breakdown (compilation vs execution)
    generation_input_tokens: int | None = None
    generation_output_tokens: int | None = None
    execution_input_tokens: int | None = None
    execution_output_tokens: int | None = None

    # LLM evaluation metrics
    match_type: str | None = None  # total_match, content_match, format_match, failure
    evaluation_score: float = 0.0
    evaluation_details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Results from running a benchmark."""

    results: list[InstanceResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def success_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.success) / len(self.results)

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time


def run_benchmark(
    instances: list[DatasetInstance],
    baseline: BaseBaseline,
    verbose: bool = False,
    evaluation_mode: EvaluationMode = "llm",
    log_dir: str | Path | None = None,
) -> BenchmarkResult:
    """Run benchmark on instances using a baseline.

    This is the ONLY benchmark runner. No special cases.

    Args:
        instances: List of DatasetInstance with {input, output_format, expected_output}
        baseline: Any baseline that implements run(TaskInput) -> BaselineResult
        verbose: Print progress
        evaluation_mode: "exact" for exact match, "llm" for semantic LLM evaluation
        log_dir: Directory to save incremental results (summary_step_N.json)

    Returns:
        BenchmarkResult with all instance results
    """
    import json

    result = BenchmarkResult()
    result.start_time = time.time()

    # Ensure log_dir is a Path
    log_path = Path(log_dir) if log_dir else None

    # Initialize LLM evaluator if needed
    llm_evaluator = LLMEvaluator() if evaluation_mode == "llm" else None

    for inst in instances:
        # Create TaskInput with context for signature grouping
        # Include output_format for compilation guidance
        task_input = TaskInput(
            task_id=inst.id,
            prompt=inst.input,
            context=inst.context,  # Pass structured context for task signature
            metadata={
                "expected_output": inst.expected_output or inst.possible_outputs,
                "output_format": inst.output_format,
            },
        )

        # Run baseline
        baseline_result = baseline.run(task_input)

        # Evaluate output
        if evaluation_mode == "llm" and llm_evaluator:
            # LLM-based semantic evaluation
            eval_result = _evaluate_with_llm(
                llm_evaluator,
                baseline_result.output,
                inst.expected_output or (inst.possible_outputs[0] if inst.possible_outputs else None),
                inst.output_format,
            )
            success = eval_result.success
            match_type = eval_result.details.get("match_type", "failure")
            evaluation_score = eval_result.score
            evaluation_details = eval_result.details
        else:
            # Exact match evaluation (backward compatible)
            success = inst.matches(baseline_result.output)
            match_type = "total_match" if success else "failure"
            evaluation_score = 1.0 if success else 0.0
            evaluation_details = {}

        # Create result with all metrics
        inst_result = InstanceResult(
            instance_id=inst.id,
            input=inst.input,
            output=baseline_result.output,
            expected=inst.expected_output or inst.possible_outputs,
            success=success,
            latency_ms=baseline_result.latency_ms,
            error=baseline_result.error,
            generation_time_ms=baseline_result.generation_time_ms,
            execution_time_ms=baseline_result.execution_time_ms,
            input_tokens=baseline_result.input_tokens,
            output_tokens=baseline_result.output_tokens,
            generation_input_tokens=baseline_result.generation_input_tokens,
            generation_output_tokens=baseline_result.generation_output_tokens,
            execution_input_tokens=baseline_result.execution_input_tokens,
            execution_output_tokens=baseline_result.execution_output_tokens,
            match_type=match_type,
            evaluation_score=evaluation_score,
            evaluation_details=evaluation_details,
        )
        result.results.append(inst_result)

        # Save incremental results to log directory
        if log_path:
            _save_incremental_results(result, log_path, len(result.results) - 1)

        if verbose:
            # Calculate running statistics
            completed = len(result.results)
            success_count = sum(1 for r in result.results if r.success)
            success_rate = success_count / completed if completed > 0 else 0
            elapsed = time.time() - result.start_time

            # Token statistics
            total_in = sum(r.input_tokens for r in result.results)
            total_out = sum(r.output_tokens for r in result.results)

            # Compilation statistics (for Code Factory)
            gen_tokens = sum((r.generation_input_tokens or 0) + (r.generation_output_tokens or 0) for r in result.results)
            exec_tokens = sum((r.execution_input_tokens or 0) + (r.execution_output_tokens or 0) for r in result.results)

            status_icons = {
                "total_match": "✓",
                "content_match": "≈",
                "format_match": "⚠",
                "failure": "✗",
            }
            status = status_icons.get(match_type, "?")

            # Print instance result
            print(f"\n{status} {inst.id} [{match_type}] (score={evaluation_score:.2f})")
            print(f"  Tokens: {baseline_result.input_tokens} in / {baseline_result.output_tokens} out")
            if baseline_result.generation_time_ms:
                print(f"  Time: {baseline_result.generation_time_ms:.0f}ms gen + {baseline_result.execution_time_ms:.0f}ms exec")
            else:
                print(f"  Time: {baseline_result.latency_ms:.0f}ms")

            # Print running statistics
            print(f"\n📊 Progress: {completed}/{len(instances)} ({completed/len(instances)*100:.1f}%)")
            print(f"   Success: {success_count}/{completed} ({success_rate*100:.1f}%)")
            print(f"   Elapsed: {elapsed:.1f}s")
            print(f"   Tokens: {total_in + total_out:,} total")
            if gen_tokens > 0:
                print(f"   - Compilation: {gen_tokens:,} | Execution: {exec_tokens:,}")

            # Print failure details
            if not success:
                print(f"\n⚠️  FAILURE DETAILS:")
                if baseline_result.error:
                    print(f"   Error: {baseline_result.error[:200]}")
                expected_preview = str(inst.expected_output or inst.possible_outputs)[:150]
                output_preview = baseline_result.output[:150]
                print(f"   Expected: {expected_preview}...")
                print(f"   Got: {output_preview}...")
                if evaluation_details.get("explanation"):
                    print(f"   Reason: {evaluation_details['explanation']}")

    result.end_time = time.time()
    return result


def _evaluate_with_llm(
    evaluator: LLMEvaluator,
    output: str,
    expected: Any,
    output_format: dict,
) -> EvaluationResult:
    """Evaluate output using LLM evaluator.

    Args:
        evaluator: LLMEvaluator instance
        output: Actual output from baseline
        expected: Expected ground truth values
        output_format: Structure description for format validation

    Returns:
        EvaluationResult with match type and score
    """
    try:
        return evaluator.evaluate(
            output=output,
            expected=expected,
            output_format=output_format,
        )
    except Exception as e:
        return EvaluationResult(
            success=False,
            score=0.0,
            error=f"LLM evaluation failed: {str(e)}",
            details={"match_type": "failure"},
        )


def _save_incremental_results(result: BenchmarkResult, log_dir: Path, step: int) -> None:
    """Save incremental results after each instance.

    Args:
        result: Current benchmark result with all completed instances
        log_dir: Directory to save results
        step: Current step number (0-indexed)
    """
    import json

    # Build summary data
    completed = len(result.results)
    success_count = sum(1 for r in result.results if r.success)
    elapsed = time.time() - result.start_time

    # Token breakdown
    total_gen_tokens = sum(
        (r.generation_input_tokens or 0) + (r.generation_output_tokens or 0)
        for r in result.results
    )
    total_exec_tokens = sum(
        (r.execution_input_tokens or 0) + (r.execution_output_tokens or 0)
        for r in result.results
    )

    summary_data = {
        "step": step,
        "completed": completed,
        "success_count": success_count,
        "success_rate": success_count / completed if completed > 0 else 0,
        "elapsed_seconds": elapsed,
        "total_tokens": total_gen_tokens + total_exec_tokens,
        "compilation_tokens": total_gen_tokens,
        "execution_tokens": total_exec_tokens,
        "instances": [
            {
                "instance_id": r.instance_id,
                "success": r.success,
                "latency_ms": r.latency_ms,
                "generation_time_ms": r.generation_time_ms,
                "execution_time_ms": r.execution_time_ms,
                "tokens": (r.generation_input_tokens or 0) + (r.generation_output_tokens or 0),
                "match_type": r.match_type,
            }
            for r in result.results
        ]
    }

    # Save to step file
    step_file = log_dir / f"summary_step_{step}.json"
    with open(step_file, "w") as f:
        json.dump(summary_data, f, indent=2)

    # Also print a compact table
    _print_results_table(result.results)


def _print_results_table(results: list[InstanceResult]) -> None:
    """Print a compact results table."""
    table = Table(
        title="Instance Results",
        box=box.ROUNDED,
        show_header=True,
    )
    table.add_column("Instance", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Latency", justify="right")
    table.add_column("Gen (ms)", justify="right", style="yellow")
    table.add_column("Exec (ms)", justify="right", style="green")
    table.add_column("Tokens", justify="right")

    for r in results:
        status = "[green]✓[/green]" if r.success else "[red]✗[/red]"
        gen_ms = f"{r.generation_time_ms:.0f}" if r.generation_time_ms else "-"
        exec_ms = f"{r.execution_time_ms:.0f}" if r.execution_time_ms else "-"
        tokens = (r.generation_input_tokens or 0) + (r.generation_output_tokens or 0)
        tokens_str = f"{tokens:,} / {(r.execution_input_tokens or 0) + (r.execution_output_tokens or 0)}"

        table.add_row(
            r.instance_id[:20],
            status,
            f"{r.latency_ms:.0f}ms",
            gen_ms,
            exec_ms,
            tokens_str,
        )

    console.print(table)


def run_benchmark_with_baseline_name(
    instances: list[DatasetInstance],
    baseline_name: str,
    verbose: bool = False,
    evaluation_mode: EvaluationMode = "llm",
    **baseline_kwargs,
) -> BenchmarkResult:
    """Run benchmark using baseline name.

    Args:
        instances: List of DatasetInstance
        baseline_name: Name of baseline ("direct_llm", "code_factory")
        verbose: Print progress
        evaluation_mode: "exact" for exact match, "llm" for semantic LLM evaluation
        **baseline_kwargs: Additional args for baseline

    Returns:
        BenchmarkResult
    """
    baseline = get_baseline(baseline_name, **baseline_kwargs)
    return run_benchmark(instances, baseline, verbose=verbose, evaluation_mode=evaluation_mode)
