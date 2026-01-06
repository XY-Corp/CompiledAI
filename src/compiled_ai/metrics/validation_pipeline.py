"""Validation pipeline metrics measuring regeneration convergence.

Based on framework.md research including:
- Quality Gate thresholds from SonarQube
- First-pass rate and regeneration tracking
- Research finding: ChatGPT achieves satisfactory solutions in ~1.6 attempts
"""

import time
from dataclasses import dataclass, field
from enum import Enum

from .base import MetricsCollector


class ValidationStage(Enum):
    """Validation pipeline stages."""

    SECURITY = "security"
    SYNTAX = "syntax"
    EXECUTION = "execution"
    ACCURACY = "accuracy"


@dataclass
class ValidationPipelineMetrics:
    """Pipeline metrics measuring regeneration convergence.

    From framework.md:
    - First-pass rate target: >70%, excellent: >90%
    - Mean regeneration attempts target: <2 (ChatGPT avg: 1.6)
    - False positive rate target: <10%

    Attributes:
        stage_attempts: Per-stage attempt counts
        stage_passes: Per-stage pass counts on first attempt
        regeneration_counts: Distribution of regeneration attempts per task
        validation_times_ms: Time spent in validation per task
    """

    stage_attempts: dict[str, int] = field(default_factory=dict)
    stage_passes: dict[str, int] = field(default_factory=dict)
    stage_failures: dict[str, int] = field(default_factory=dict)

    # Track regeneration attempts per task
    regeneration_counts: list[int] = field(default_factory=list)

    # Timing
    validation_times_ms: list[float] = field(default_factory=list)
    current_start_time: float = 0.0

    # False positive tracking
    false_positives: int = 0
    total_rejections: int = 0

    # Thresholds from framework.md
    FIRST_PASS_COMPETITIVE = 0.70
    FIRST_PASS_EXCELLENT = 0.90
    MEAN_REGEN_TARGET = 2.0
    MEAN_REGEN_EXCELLENT = 1.6  # ChatGPT average
    FALSE_POSITIVE_TARGET = 0.10

    # Quality gate defaults
    QUALITY_GATE = {
        "coverage_lines": 0.80,
        "coverage_branches": 0.75,
        "complexity_cognitive": 15,
        "complexity_cyclomatic": 10,
        "critical_vulns": 0,
        "duplication": 0.03,
        "maintainability_rating": "B",
    }

    def start_validation(self) -> None:
        """Start timing a validation run."""
        self.current_start_time = time.perf_counter()

    def end_validation(self, regen_attempts: int) -> None:
        """End timing and record regeneration attempts.

        Args:
            regen_attempts: Number of regeneration attempts for this task
        """
        elapsed_ms = (time.perf_counter() - self.current_start_time) * 1000
        self.validation_times_ms.append(elapsed_ms)
        self.regeneration_counts.append(regen_attempts)

    def record_stage_result(
        self, stage: ValidationStage, passed: bool, first_attempt: bool = True
    ) -> None:
        """Record a validation stage result.

        Args:
            stage: The validation stage
            passed: Whether validation passed
            first_attempt: Whether this was the first attempt (for first-pass rate)
        """
        stage_key = stage.value
        self.stage_attempts[stage_key] = self.stage_attempts.get(stage_key, 0) + 1

        if passed and first_attempt:
            self.stage_passes[stage_key] = self.stage_passes.get(stage_key, 0) + 1
        elif not passed:
            self.stage_failures[stage_key] = self.stage_failures.get(stage_key, 0) + 1

    def record_false_positive(self) -> None:
        """Record a false positive (incorrectly rejected valid code)."""
        self.false_positives += 1
        self.total_rejections += 1

    def record_true_rejection(self) -> None:
        """Record a true rejection (correctly rejected invalid code)."""
        self.total_rejections += 1

    @property
    def total_validations(self) -> int:
        """Total number of validation runs."""
        return len(self.regeneration_counts)

    def stage_first_pass_rate(self, stage: ValidationStage) -> float:
        """First-pass rate for a specific stage.

        Args:
            stage: The validation stage

        Returns:
            Percentage passing on first attempt
        """
        stage_key = stage.value
        attempts = self.stage_attempts.get(stage_key, 0)
        if attempts == 0:
            return 0.0
        passes = self.stage_passes.get(stage_key, 0)
        return passes / attempts

    @property
    def overall_first_pass_rate(self) -> float:
        """Overall first-pass rate (pass all stages without regeneration).

        Target: >70%, excellent: >90%.
        """
        if not self.regeneration_counts:
            return 0.0
        # Count tasks with 0 regeneration attempts
        first_pass_count = sum(1 for r in self.regeneration_counts if r == 0)
        return first_pass_count / len(self.regeneration_counts)

    @property
    def mean_regen_attempts(self) -> float:
        """Mean regeneration attempts per task.

        Target: <2, excellent: <1.6 (ChatGPT average).
        """
        if not self.regeneration_counts:
            return 0.0
        return sum(self.regeneration_counts) / len(self.regeneration_counts)

    @property
    def max_regen_attempts(self) -> int:
        """Maximum regeneration attempts for any task."""
        if not self.regeneration_counts:
            return 0
        return max(self.regeneration_counts)

    @property
    def time_to_valid_ms(self) -> float:
        """Mean time to valid artifact (ms)."""
        if not self.validation_times_ms:
            return 0.0
        return sum(self.validation_times_ms) / len(self.validation_times_ms)

    @property
    def false_positive_rate(self) -> float:
        """False positive rate: false_rejections / total_rejections.

        Target: <10%.
        """
        if self.total_rejections == 0:
            return 0.0
        return self.false_positives / self.total_rejections

    @property
    def cumulative_pass_rate(self) -> float:
        """Cumulative pass rate: ∏(Stage_Pass_Rate)."""
        if not self.stage_attempts:
            return 0.0

        cumulative = 1.0
        for stage in ValidationStage:
            rate = self.stage_first_pass_rate(stage)
            if rate > 0:  # Only multiply if we have data for this stage
                cumulative *= rate

        return cumulative

    def regen_distribution(self) -> dict[str, int]:
        """Distribution of regeneration attempts.

        Returns:
            Dict with keys "0", "1", "2", "3", "4+" and counts
        """
        distribution: dict[str, int] = {"0": 0, "1": 0, "2": 0, "3": 0, "4+": 0}
        for count in self.regeneration_counts:
            if count >= 4:
                distribution["4+"] += 1
            else:
                distribution[str(count)] += 1
        return distribution

    def is_competitive(self) -> bool:
        """Check if metrics meet competitive thresholds."""
        return (
            self.overall_first_pass_rate >= self.FIRST_PASS_COMPETITIVE
            and self.mean_regen_attempts <= self.MEAN_REGEN_TARGET
        )

    def is_excellent(self) -> bool:
        """Check if metrics meet excellent thresholds."""
        return (
            self.overall_first_pass_rate >= self.FIRST_PASS_EXCELLENT
            and self.mean_regen_attempts <= self.MEAN_REGEN_EXCELLENT
        )

    def to_collector(self, collector: MetricsCollector | None = None) -> MetricsCollector:
        """Export metrics to a collector.

        Args:
            collector: Existing collector to add to, or None to create new

        Returns:
            MetricsCollector with validation pipeline metrics
        """
        collector = collector or MetricsCollector()

        # Per-stage first-pass rates
        for stage in ValidationStage:
            rate = self.stage_first_pass_rate(stage)
            collector.record(
                f"{stage.value}_first_pass_rate", rate, "ratio", "validation_pipeline"
            )

        # Overall metrics
        collector.record(
            "overall_first_pass_rate",
            self.overall_first_pass_rate,
            "ratio",
            "validation_pipeline",
        )
        collector.record(
            "mean_regen_attempts",
            self.mean_regen_attempts,
            "count",
            "validation_pipeline",
        )
        collector.record(
            "max_regen_attempts",
            self.max_regen_attempts,
            "count",
            "validation_pipeline",
        )
        collector.record(
            "time_to_valid_ms", self.time_to_valid_ms, "ms", "validation_pipeline"
        )
        collector.record(
            "false_positive_rate",
            self.false_positive_rate,
            "ratio",
            "validation_pipeline",
        )
        collector.record(
            "cumulative_pass_rate",
            self.cumulative_pass_rate,
            "ratio",
            "validation_pipeline",
        )
        collector.record(
            "total_validations", self.total_validations, "count", "validation_pipeline"
        )

        # Regeneration distribution
        dist = self.regen_distribution()
        for key, count in dist.items():
            collector.record(
                f"regen_count_{key}", count, "count", "validation_pipeline"
            )

        # Thresholds
        collector.record(
            "is_competitive", self.is_competitive(), "bool", "validation_pipeline"
        )
        collector.record(
            "is_excellent", self.is_excellent(), "bool", "validation_pipeline"
        )

        return collector
