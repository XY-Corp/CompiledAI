"""Compilation and execution metrics tracking for scientific analysis."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from .task_signature import TaskSignature


@dataclass
class CompilationStats:
    """
    Statistics for a single compiled workflow.

    Tracks both one-time compilation cost and ongoing execution
    statistics to enable cost amortization analysis and break-even
    point calculation.

    Attributes:
        signature: Task signature this workflow was compiled for
        compilation_task_id: Task ID that triggered compilation
        compilation_tokens: Tokens consumed during compilation
        compilation_latency_ms: Time taken to compile (milliseconds)
        compiled_at: Timestamp when compilation occurred
        execution_count: Number of times workflow has been executed
        total_execution_latency_ms: Cumulative execution time
        success_count: Number of successful executions
        failure_count: Number of failed executions
    """

    signature: TaskSignature
    compilation_task_id: str
    compilation_tokens: int
    compilation_latency_ms: float
    compiled_at: datetime
    execution_count: int = 0
    total_execution_latency_ms: float = 0.0
    success_count: int = 0
    failure_count: int = 0


class CompilationMetricsTracker:
    """
    Track compilation and execution metrics per task signature.

    Enables scientific analysis for publication:
    - Cost amortization calculation (tokens saved vs DirectLLM)
    - Break-even point determination (N* tasks needed)
    - Per-task-type success rates
    - Latency comparisons
    - Workflow reuse statistics

    The tracker maintains separate statistics for each unique task
    signature, allowing detailed analysis of which task types benefit
    most from the compile-once-execute-many approach.

    Example:
        >>> tracker = CompilationMetricsTracker()
        >>> # Task 1: compilation
        >>> tracker.record_compilation(sig, tokens=10000, latency_ms=5000, task_id="task_1")
        >>> # Task 2-10: execution (reusing compiled workflow)
        >>> for i in range(2, 11):
        ...     tracker.record_execution(sig, tokens=0, latency_ms=100, success=True)
        >>> # Generate report
        >>> report = tracker.get_amortization_report()
        >>> print(f"Break-even point: {report['by_signature'][0]['break_even_n']}")
    """

    def __init__(self):
        """Initialize metrics tracker with empty statistics."""
        self._stats: Dict[TaskSignature, CompilationStats] = {}

    def record_compilation(
        self, signature: TaskSignature, tokens: int, latency_ms: float, task_id: str
    ) -> None:
        """
        Record compilation event for a new task signature.

        This should be called once per unique task signature when a
        workflow is first compiled.

        Args:
            signature: Task signature being compiled
            tokens: Tokens consumed during compilation
            latency_ms: Compilation time in milliseconds
            task_id: Task ID that triggered compilation

        Example:
            >>> tracker.record_compilation(
            ...     signature=sig,
            ...     tokens=10000,
            ...     latency_ms=4500,
            ...     task_id="classification_01"
            ... )
        """
        self._stats[signature] = CompilationStats(
            signature=signature,
            compilation_task_id=task_id,
            compilation_tokens=tokens,
            compilation_latency_ms=latency_ms,
            compiled_at=datetime.now(),
        )

    def record_execution(
        self,
        signature: TaskSignature,
        tokens: int,
        latency_ms: float,
        success: bool = True,
    ) -> None:
        """
        Record execution event for an existing compiled workflow.

        This should be called each time a cached workflow is reused.
        For compiled workflows, tokens should always be 0.

        Args:
            signature: Task signature of cached workflow being executed
            tokens: Tokens consumed (should be 0 for compiled execution)
            latency_ms: Execution time in milliseconds
            success: Whether execution succeeded

        Example:
            >>> tracker.record_execution(
            ...     signature=sig,
            ...     tokens=0,  # Compiled code, no LLM call
            ...     latency_ms=150,
            ...     success=True
            ... )
        """
        if signature not in self._stats:
            # This shouldn't happen, but handle gracefully
            return

        stats = self._stats[signature]
        stats.execution_count += 1
        stats.total_execution_latency_ms += latency_ms

        if success:
            stats.success_count += 1
        else:
            stats.failure_count += 1

    def update_execution_latency(
        self, signature: TaskSignature, latency_ms: float
    ) -> None:
        """
        Update latency for most recent execution.

        Used when execution latency needs to be recorded after
        initial record_execution call (e.g., when latency wasn't
        known at recording time).

        Args:
            signature: Task signature of executed workflow
            latency_ms: Actual execution latency in milliseconds
        """
        if signature in self._stats:
            stats = self._stats[signature]
            # Add to total (assuming last execution had 0 latency)
            stats.total_execution_latency_ms += latency_ms

    def get_compilation_tokens(self, signature: TaskSignature) -> int:
        """
        Get compilation tokens for a specific signature.

        Args:
            signature: Task signature to query

        Returns:
            Compilation tokens, or 0 if signature not found

        Example:
            >>> tokens = tracker.get_compilation_tokens(sig)
            >>> print(f"Compilation cost: {tokens} tokens")
        """
        if signature in self._stats:
            return self._stats[signature].compilation_tokens
        return 0

    def get_amortization_report(
        self, direct_llm_tokens_per_task: int = 1500
    ) -> Dict:
        """
        Generate scientific report on cost amortization.

        Calculates break-even points, cost savings, and success rates
        for each compiled workflow. Compares against DirectLLM baseline
        to demonstrate value proposition.

        Args:
            direct_llm_tokens_per_task: Average tokens used by DirectLLM
                baseline per task. Default is 1500 (typical for GPT-4).

        Returns:
            Dictionary with amortization analysis:
            - total_compilations: Number of unique workflows compiled
            - total_executions: Total execution count across all workflows
            - by_signature: Per-workflow statistics including:
                - category: Task category
                - compilation_tokens: One-time compilation cost
                - execution_count: Times workflow was reused
                - amortized_tokens_per_task: Average cost per task
                - break_even_n: Tasks needed to break even with DirectLLM
                - total_tokens_saved: Tokens saved vs DirectLLM
                - savings_percentage: Cost reduction percentage
                - success_rate: Fraction of successful executions
                - avg_execution_latency_ms: Mean execution time

        Example:
            >>> report = tracker.get_amortization_report(direct_llm_tokens_per_task=1500)
            >>> for sig_data in report['by_signature']:
            ...     print(f"{sig_data['category']}: Break-even at {sig_data['break_even_n']} tasks")
            ...     print(f"  Savings: {sig_data['savings_percentage']}%")
        """
        report = {
            "total_compilations": len(self._stats),
            "total_executions": sum(s.execution_count for s in self._stats.values()),
            "by_signature": [],
        }

        for sig, stats in self._stats.items():
            # Calculate total executions (compilation task + reuses)
            total_executions = stats.execution_count + 1

            # Calculate amortized cost per task
            amortized_tokens_per_task = stats.compilation_tokens / total_executions

            # Calculate break-even point: N* = compilation_cost / (direct_llm_cost - compiled_cost)
            # Since compiled cost is 0, this simplifies to: N* = compilation_cost / direct_llm_cost
            break_even_n = stats.compilation_tokens / direct_llm_tokens_per_task

            # Calculate cost savings vs DirectLLM
            direct_llm_total_cost = total_executions * direct_llm_tokens_per_task
            compiled_total_cost = stats.compilation_tokens  # + 0 for each execution
            savings = direct_llm_total_cost - compiled_total_cost
            savings_pct = (
                (savings / direct_llm_total_cost * 100)
                if direct_llm_total_cost > 0
                else 0
            )

            # Calculate success rate
            success_rate = stats.success_count / total_executions if total_executions > 0 else 0

            # Calculate average execution latency
            avg_execution_latency_ms = (
                stats.total_execution_latency_ms / stats.execution_count
                if stats.execution_count > 0
                else 0
            )

            sig_report = {
                "category": sig.category,
                "compilation_tokens": stats.compilation_tokens,
                "execution_count": stats.execution_count,
                "amortized_tokens_per_task": round(amortized_tokens_per_task, 2),
                "break_even_n": round(break_even_n, 2),
                "total_tokens_saved": savings,
                "savings_percentage": round(savings_pct, 2),
                "success_rate": round(success_rate, 3),
                "avg_execution_latency_ms": round(avg_execution_latency_ms, 2),
            }

            report["by_signature"].append(sig_report)

        return report
