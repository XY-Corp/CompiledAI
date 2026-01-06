"""Latency metrics for benchmark evaluation."""

import statistics
from dataclasses import dataclass, field

from .base import MetricsCollector


@dataclass
class LatencyMetrics:
    """Latency metrics for a workflow or system.

    Based on MLCommons/MLPerf Inference standards for LLM latency benchmarking.
    See framework.md for detailed thresholds and requirements.

    Attributes:
        measurements: List of latency measurements in milliseconds
        cold_start_ms: Time for initial cold start (e.g., code generation)
        ttft_samples: Time to First Token measurements (for streaming)
        tpot_samples: Time Per Output Token measurements
    """

    measurements: list[float] = field(default_factory=list)
    cold_start_ms: float = 0.0
    ttft_samples: list[float] = field(default_factory=list)  # Time to First Token
    tpot_samples: list[float] = field(default_factory=list)  # Time Per Output Token

    # MLPerf standard thresholds (from framework.md)
    TTFT_ACCEPTABLE = 2000.0  # ms - MLPerf constraint for LLAMA2-70B
    TTFT_GOOD = 500.0         # ms
    TTFT_EXCELLENT = 200.0    # ms

    TPOT_ACCEPTABLE = 200.0   # ms - ~240 words/minute reading speed
    TPOT_GOOD = 50.0          # ms
    TPOT_EXCELLENT = 10.0     # ms

    # Minimum samples for stable P99 estimation
    MIN_SAMPLES_FOR_P99 = 1000

    def record(self, latency_ms: float) -> None:
        """Record a latency measurement.

        Args:
            latency_ms: Latency in milliseconds
        """
        self.measurements.append(latency_ms)

    def record_cold_start(self, latency_ms: float) -> None:
        """Record cold start latency.

        Args:
            latency_ms: Cold start latency in milliseconds
        """
        self.cold_start_ms = latency_ms

    def record_ttft(self, ttft_ms: float) -> None:
        """Record Time to First Token measurement.

        Args:
            ttft_ms: Time to first token in milliseconds
        """
        self.ttft_samples.append(ttft_ms)

    def record_tpot(self, tpot_ms: float) -> None:
        """Record Time Per Output Token measurement.

        Args:
            tpot_ms: Time per output token in milliseconds
        """
        self.tpot_samples.append(tpot_ms)

    def record_streaming_response(
        self, ttft_ms: float, total_ms: float, output_tokens: int
    ) -> None:
        """Record a complete streaming response with derived metrics.

        Args:
            ttft_ms: Time to first token
            total_ms: Total end-to-end latency
            output_tokens: Number of output tokens generated
        """
        self.record(total_ms)
        self.record_ttft(ttft_ms)

        # Calculate ITL: (E2E_latency - TTFT) / (Output_tokens - 1)
        if output_tokens > 1:
            itl = (total_ms - ttft_ms) / (output_tokens - 1)
            self.record_tpot(itl)

    @property
    def count(self) -> int:
        """Number of measurements recorded."""
        return len(self.measurements)

    @property
    def p50_ms(self) -> float:
        """50th percentile (median) latency."""
        if not self.measurements:
            return 0.0
        return statistics.median(self.measurements)

    @property
    def p90_ms(self) -> float:
        """90th percentile latency."""
        if not self.measurements:
            return 0.0
        return self._percentile(90)

    @property
    def p95_ms(self) -> float:
        """95th percentile latency."""
        if not self.measurements:
            return 0.0
        return self._percentile(95)

    @property
    def p99_ms(self) -> float:
        """99th percentile latency."""
        if not self.measurements:
            return 0.0
        return self._percentile(99)

    @property
    def jitter_ms(self) -> float:
        """Jitter: P99 - P50.

        Lower is better. Compiled AI should have near-zero jitter.
        """
        return self.p99_ms - self.p50_ms

    @property
    def mean_ms(self) -> float:
        """Mean latency."""
        if not self.measurements:
            return 0.0
        return statistics.mean(self.measurements)

    @property
    def stdev_ms(self) -> float:
        """Standard deviation of latency."""
        if len(self.measurements) < 2:
            return 0.0
        return statistics.stdev(self.measurements)

    @property
    def min_ms(self) -> float:
        """Minimum latency."""
        if not self.measurements:
            return 0.0
        return min(self.measurements)

    @property
    def max_ms(self) -> float:
        """Maximum latency."""
        if not self.measurements:
            return 0.0
        return max(self.measurements)

    # MLPerf standard metrics
    @property
    def ttft_ms(self) -> float:
        """Median Time to First Token (TTFT).

        MLPerf constraint: <2000ms for LLAMA2-70B.
        """
        if not self.ttft_samples:
            return 0.0
        return statistics.median(self.ttft_samples)

    @property
    def ttft_p99_ms(self) -> float:
        """P99 Time to First Token."""
        if not self.ttft_samples:
            return 0.0
        return self._percentile_of(self.ttft_samples, 99)

    @property
    def tpot_ms(self) -> float:
        """Median Time Per Output Token (TPOT) / Inter-Token Latency (ITL).

        MLPerf constraint: <200ms (~240 words/minute reading speed).
        """
        if not self.tpot_samples:
            return 0.0
        return statistics.median(self.tpot_samples)

    @property
    def tpot_p99_ms(self) -> float:
        """P99 Time Per Output Token."""
        if not self.tpot_samples:
            return 0.0
        return self._percentile_of(self.tpot_samples, 99)

    @property
    def has_sufficient_samples(self) -> bool:
        """Check if we have enough samples for stable P99 estimation.

        From framework.md: P99 requires 1000+ samples for stable estimation.
        """
        return len(self.measurements) >= self.MIN_SAMPLES_FOR_P99

    def _percentile_of(self, data: list[float], p: float) -> float:
        """Calculate percentile of arbitrary data list."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        n = len(sorted_data)
        k = (n - 1) * (p / 100)
        f = int(k)
        c = k - f
        if f + 1 < n:
            return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
        return sorted_data[f]

    def _percentile(self, p: float) -> float:
        """Calculate the p-th percentile.

        Args:
            p: Percentile (0-100)

        Returns:
            Value at the p-th percentile
        """
        if not self.measurements:
            return 0.0

        sorted_data = sorted(self.measurements)
        n = len(sorted_data)
        k = (n - 1) * (p / 100)
        f = int(k)
        c = k - f

        if f + 1 < n:
            return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
        return sorted_data[f]

    def meets_sla(
        self,
        p50_target: float = 100.0,
        p99_target: float = 500.0,
        jitter_target: float = 100.0,
    ) -> bool:
        """Check if latency meets SLA targets.

        Args:
            p50_target: Target P50 latency in ms (default: 100ms)
            p99_target: Target P99 latency in ms (default: 500ms)
            jitter_target: Target jitter in ms (default: 100ms)

        Returns:
            True if all targets are met
        """
        return (
            self.p50_ms <= p50_target
            and self.p99_ms <= p99_target
            and self.jitter_ms <= jitter_target
        )

    def meets_mlperf_constraints(self) -> dict[str, bool]:
        """Check if latency meets MLPerf constraints.

        Returns:
            Dictionary with constraint check results
        """
        return {
            "ttft_acceptable": self.ttft_ms <= self.TTFT_ACCEPTABLE,
            "ttft_good": self.ttft_ms <= self.TTFT_GOOD,
            "ttft_excellent": self.ttft_ms <= self.TTFT_EXCELLENT,
            "tpot_acceptable": self.tpot_ms <= self.TPOT_ACCEPTABLE,
            "tpot_good": self.tpot_ms <= self.TPOT_GOOD,
            "tpot_excellent": self.tpot_ms <= self.TPOT_EXCELLENT,
            "sufficient_samples": self.has_sufficient_samples,
        }

    def get_rating(self) -> str:
        """Get overall latency rating based on MLPerf thresholds.

        Returns:
            'excellent', 'good', 'acceptable', or 'poor'
        """
        constraints = self.meets_mlperf_constraints()
        if constraints["ttft_excellent"] and constraints["tpot_excellent"]:
            return "excellent"
        elif constraints["ttft_good"] and constraints["tpot_good"]:
            return "good"
        elif constraints["ttft_acceptable"] and constraints["tpot_acceptable"]:
            return "acceptable"
        return "poor"

    def to_collector(self, collector: MetricsCollector | None = None) -> MetricsCollector:
        """Export metrics to a collector.

        Args:
            collector: Existing collector to add to, or None to create new

        Returns:
            MetricsCollector with latency metrics
        """
        collector = collector or MetricsCollector()

        # Standard percentiles
        collector.record("p50_latency", self.p50_ms, "ms", "latency")
        collector.record("p90_latency", self.p90_ms, "ms", "latency")
        collector.record("p95_latency", self.p95_ms, "ms", "latency")
        collector.record("p99_latency", self.p99_ms, "ms", "latency")
        collector.record("jitter", self.jitter_ms, "ms", "latency")

        # Basic stats
        collector.record("mean_latency", self.mean_ms, "ms", "latency")
        collector.record("stdev_latency", self.stdev_ms, "ms", "latency")
        collector.record("min_latency", self.min_ms, "ms", "latency")
        collector.record("max_latency", self.max_ms, "ms", "latency")
        collector.record("cold_start", self.cold_start_ms, "ms", "latency")
        collector.record("measurement_count", self.count, "count", "latency")

        # MLPerf standard metrics
        collector.record("ttft", self.ttft_ms, "ms", "latency")
        collector.record("ttft_p99", self.ttft_p99_ms, "ms", "latency")
        collector.record("tpot", self.tpot_ms, "ms", "latency")
        collector.record("tpot_p99", self.tpot_p99_ms, "ms", "latency")

        # Sample sufficiency
        collector.record(
            "has_sufficient_samples", self.has_sufficient_samples, "bool", "latency"
        )

        # Rating
        collector.record("rating", self.get_rating(), "category", "latency")

        return collector


@dataclass
class LatencyComparison:
    """Compare latency between multiple approaches."""

    compiled: LatencyMetrics
    runtime: LatencyMetrics

    def jitter_improvement(self) -> float:
        """Calculate jitter improvement ratio.

        Returns:
            Ratio of runtime jitter to compiled jitter.
            Higher is better (compiled has less jitter).
        """
        if self.compiled.jitter_ms == 0:
            return float("inf") if self.runtime.jitter_ms > 0 else 1.0
        return self.runtime.jitter_ms / self.compiled.jitter_ms

    def p50_improvement(self) -> float:
        """Calculate P50 improvement ratio.

        Returns:
            Ratio of runtime P50 to compiled P50.
            Higher is better (compiled is faster).
        """
        if self.compiled.p50_ms == 0:
            return float("inf") if self.runtime.p50_ms > 0 else 1.0
        return self.runtime.p50_ms / self.compiled.p50_ms

    def p99_improvement(self) -> float:
        """Calculate P99 improvement ratio.

        Returns:
            Ratio of runtime P99 to compiled P99.
            Higher is better (compiled is faster at tail).
        """
        if self.compiled.p99_ms == 0:
            return float("inf") if self.runtime.p99_ms > 0 else 1.0
        return self.runtime.p99_ms / self.compiled.p99_ms

    def to_collector(self, collector: MetricsCollector | None = None) -> MetricsCollector:
        """Export comparison metrics to a collector.

        Args:
            collector: Existing collector to add to, or None to create new

        Returns:
            MetricsCollector with comparison metrics
        """
        collector = collector or MetricsCollector()

        # Add individual metrics
        self.compiled.to_collector(collector)

        # Add comparison metrics
        collector.record(
            "p50_improvement", self.p50_improvement(), "ratio", "latency_comparison"
        )
        collector.record(
            "p99_improvement", self.p99_improvement(), "ratio", "latency_comparison"
        )
        collector.record(
            "jitter_improvement", self.jitter_improvement(), "ratio", "latency_comparison"
        )

        return collector
