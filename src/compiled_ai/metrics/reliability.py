"""Reliability metrics for workflow completion and error tracking.

Based on framework.md research including:
- AgentBench (ICLR 2024) systematic LLM-as-Agent evaluation
- τ-Bench (Yao et al., 2024) airline domain workflows
- CLASSic Framework (ICLR 2025 Workshop) five-dimensional evaluation
- ToolEmu safety benchmark
"""

from dataclasses import dataclass, field
from enum import Enum

from .base import MetricsCollector


class FailureMode(Enum):
    """Categories of failure modes to track (from framework.md)."""

    TOOL_SELECTION = "tool_selection"
    PARAMETER_ERROR = "parameter_error"
    REASONING_FAILURE = "reasoning_failure"
    CONTEXT_LOSS = "context_loss"
    TIMEOUT = "timeout"
    INFINITE_LOOP = "infinite_loop"
    SECURITY_VIOLATION = "security_violation"
    UNKNOWN = "unknown"


@dataclass
class ReliabilityMetrics:
    """Reliability metrics from AgentBench, τ-Bench, CLASSic framework.

    From framework.md:
    - Salesforce reports ~35% success rate in multi-turn business scenarios
    - Cemri et al. found 41-87% failure rates across 150 multi-agent systems

    Attributes:
        total_tasks: Total number of tasks attempted
        completed_tasks: Number of successfully completed tasks
        failed_tasks: Number of failed tasks
        failure_modes: Counter of failure modes encountered
    """

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    failure_modes: dict[str, int] = field(default_factory=dict)

    # Milestone tracking for partial completion
    milestones_achieved: float = 0.0
    milestones_total: float = 0.0

    # Recovery tracking
    recovery_attempts: int = 0
    successful_recoveries: int = 0

    # Competitive thresholds from framework.md
    TASK_COMPLETION_BASELINE = 0.35    # Agent baseline from Salesforce
    TASK_COMPLETION_COMPETITIVE = 0.50  # >50% is competitive
    TASK_COMPLETION_EXCELLENT = 0.75    # >75% is excellent

    def record_task_success(self) -> None:
        """Record a successfully completed task."""
        self.total_tasks += 1
        self.completed_tasks += 1

    def record_task_failure(self, mode: FailureMode = FailureMode.UNKNOWN) -> None:
        """Record a failed task with failure mode.

        Args:
            mode: The failure mode category
        """
        self.total_tasks += 1
        self.failed_tasks += 1
        mode_key = mode.value
        self.failure_modes[mode_key] = self.failure_modes.get(mode_key, 0) + 1

    def record_milestone(self, achieved: float, total: float) -> None:
        """Record milestone progress for a task.

        Args:
            achieved: Sum of achieved milestone weights
            total: Sum of all milestone weights
        """
        self.milestones_achieved += achieved
        self.milestones_total += total

    def record_recovery_attempt(self, successful: bool) -> None:
        """Record a recovery attempt.

        Args:
            successful: Whether the recovery was successful
        """
        self.recovery_attempts += 1
        if successful:
            self.successful_recoveries += 1

    @property
    def task_completion_rate(self) -> float:
        """Task completion rate: Successfully_completed / Total_attempted.

        Target: >50% competitive, >75% excellent.
        Baseline: ~35% (multi-turn business scenarios)
        """
        if self.total_tasks == 0:
            return 0.0
        return self.completed_tasks / self.total_tasks

    @property
    def error_rate(self) -> float:
        """Error rate: Failed / Total."""
        if self.total_tasks == 0:
            return 0.0
        return self.failed_tasks / self.total_tasks

    @property
    def milestone_progress(self) -> float:
        """Milestone-based progress: Σ(weight × achieved) / Σ weights."""
        if self.milestones_total == 0:
            return 0.0
        return self.milestones_achieved / self.milestones_total

    @property
    def recovery_rate(self) -> float:
        """Recovery success rate."""
        if self.recovery_attempts == 0:
            return 0.0
        return self.successful_recoveries / self.recovery_attempts

    @property
    def dominant_failure_mode(self) -> str | None:
        """Most common failure mode."""
        if not self.failure_modes:
            return None
        return max(self.failure_modes, key=self.failure_modes.get)  # type: ignore

    def improvement_over_baseline(self) -> float:
        """Calculate improvement over agent baseline (35%).

        Returns:
            Ratio of completion rate to baseline. >1 means better than baseline.
        """
        return self.task_completion_rate / self.TASK_COMPLETION_BASELINE

    def is_competitive(self) -> bool:
        """Check if metrics meet competitive thresholds."""
        return self.task_completion_rate >= self.TASK_COMPLETION_COMPETITIVE

    def is_excellent(self) -> bool:
        """Check if metrics meet excellent thresholds."""
        return self.task_completion_rate >= self.TASK_COMPLETION_EXCELLENT

    def to_collector(self, collector: MetricsCollector | None = None) -> MetricsCollector:
        """Export metrics to a collector.

        Args:
            collector: Existing collector to add to, or None to create new

        Returns:
            MetricsCollector with reliability metrics
        """
        collector = collector or MetricsCollector()

        # Core metrics
        collector.record("total_tasks", self.total_tasks, "count", "reliability")
        collector.record("completed_tasks", self.completed_tasks, "count", "reliability")
        collector.record("failed_tasks", self.failed_tasks, "count", "reliability")
        collector.record(
            "task_completion_rate", self.task_completion_rate, "ratio", "reliability"
        )
        collector.record("error_rate", self.error_rate, "ratio", "reliability")

        # Milestone progress
        collector.record(
            "milestone_progress", self.milestone_progress, "ratio", "reliability"
        )

        # Recovery
        collector.record("recovery_attempts", self.recovery_attempts, "count", "reliability")
        collector.record("recovery_rate", self.recovery_rate, "ratio", "reliability")

        # Failure modes
        for mode, count in self.failure_modes.items():
            collector.record(f"failure_mode_{mode}", count, "count", "reliability")

        if self.dominant_failure_mode:
            collector.record(
                "dominant_failure_mode", self.dominant_failure_mode, "category", "reliability"
            )

        # Comparison to baseline
        collector.record(
            "improvement_over_baseline",
            self.improvement_over_baseline(),
            "ratio",
            "reliability",
        )

        # Thresholds
        collector.record("is_competitive", self.is_competitive(), "bool", "reliability")
        collector.record("is_excellent", self.is_excellent(), "bool", "reliability")

        return collector


@dataclass
class CLASSicMetrics:
    """CLASSic Framework five-dimensional evaluation (ICLR 2025 Workshop).

    Dimensions:
    - Cost: API usage, token consumption, infrastructure overhead
    - Latency: End-to-end response time
    - Accuracy: Workflow selection correctness (best: 76.1%)
    - Stability: Consistency across diverse inputs (domain-specific: 72%)
    - Security: Resilience to adversarial inputs, prompt injection
    """

    cost_score: float = 0.0         # Normalized cost (lower is better)
    latency_score: float = 0.0      # Normalized latency (lower is better)
    accuracy_score: float = 0.0     # Workflow selection correctness
    stability_score: float = 0.0    # Consistency across inputs
    security_score: float = 0.0     # Adversarial resilience

    # Thresholds from framework.md
    ACCURACY_BEST = 0.761           # Best reported accuracy
    STABILITY_DOMAIN = 0.72         # Domain-specific stability

    @property
    def composite_score(self) -> float:
        """Weighted composite score (customize weights as needed)."""
        # Equal weighting by default
        return (
            self.accuracy_score * 0.3
            + self.stability_score * 0.25
            + self.security_score * 0.25
            + (1 - self.cost_score) * 0.1  # Invert cost (lower is better)
            + (1 - self.latency_score) * 0.1  # Invert latency
        )

    def to_collector(self, collector: MetricsCollector | None = None) -> MetricsCollector:
        """Export CLASSic metrics to a collector."""
        collector = collector or MetricsCollector()

        collector.record("classic_cost", self.cost_score, "score", "reliability")
        collector.record("classic_latency", self.latency_score, "score", "reliability")
        collector.record("classic_accuracy", self.accuracy_score, "score", "reliability")
        collector.record("classic_stability", self.stability_score, "score", "reliability")
        collector.record("classic_security", self.security_score, "score", "reliability")
        collector.record("classic_composite", self.composite_score, "score", "reliability")

        return collector
