"""Consistency and determinism metrics for compiled vs runtime comparison.

Based on framework.md research including:
- Semantic Entropy (Farquhar et al., Nature 2024)
- SelfCheckGPT (EMNLP 2023)
- JSONSchemaBench schema conformance
- Critical finding: temperature=0 provides NO determinism guarantee
"""

import hashlib
import math
from collections import Counter
from dataclasses import dataclass, field

from .base import MetricsCollector


@dataclass
class ConsistencyMetrics:
    """Consistency metrics measuring output determinism and reproducibility.

    Critical insight from framework.md: Testing Qwen3-235B at temperature=0
    with 1,000 identical completions produced 80 unique outputs.

    Attributes:
        outputs: List of output strings for identical inputs
        output_hashes: List of hashed outputs for efficient comparison
    """

    outputs: list[str] = field(default_factory=list)
    output_hashes: list[str] = field(default_factory=list)

    # Competitive thresholds from framework.md
    EXACT_MATCH_COMPETITIVE = 0.80    # >80% is competitive
    EXACT_MATCH_EXCELLENT = 0.95      # >95% is excellent
    BERT_SCORE_COMPETITIVE = 0.85     # >0.85 is competitive
    BERT_SCORE_EXCELLENT = 0.95       # >0.95 is excellent

    # Minimum samples for rigorous testing
    MIN_SAMPLES_BASIC = 50
    MIN_SAMPLES_RIGOROUS = 1000

    def record_output(self, output: str) -> None:
        """Record an output for consistency analysis.

        Args:
            output: The output string to record
        """
        self.outputs.append(output)
        # Hash for efficient duplicate detection
        output_hash = hashlib.sha256(output.encode()).hexdigest()
        self.output_hashes.append(output_hash)

    @property
    def sample_size(self) -> int:
        """Number of outputs recorded."""
        return len(self.outputs)

    @property
    def unique_outputs(self) -> int:
        """Count of unique outputs.

        For perfectly deterministic systems, this should be 1.
        Qwen3-235B at temp=0 produced 80 unique outputs in 1000 runs!
        """
        return len(set(self.output_hashes))

    @property
    def exact_match_rate(self) -> float:
        """Percentage of outputs identical to the most common output.

        Target: >80% competitive, >95% excellent.
        """
        if not self.output_hashes:
            return 0.0
        counter = Counter(self.output_hashes)
        most_common_count = counter.most_common(1)[0][1]
        return most_common_count / len(self.output_hashes)

    @property
    def output_entropy(self) -> float:
        """Shannon entropy of output distribution.

        H = -Σ p_i log₂ p_i

        For deterministic output, entropy = 0.
        Higher entropy = more variability.
        """
        if not self.output_hashes:
            return 0.0

        counter = Counter(self.output_hashes)
        total = len(self.output_hashes)
        probs = [count / total for count in counter.values()]

        entropy = 0.0
        for p in probs:
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy

    @property
    def semantic_entropy(self) -> float:
        """Semantic entropy over meaning clusters.

        H_s = -Σ P(g_j) log₂ P(g_j) where g_j represents semantic groups.

        Note: Full implementation requires semantic clustering (e.g., via embeddings).
        This simplified version uses exact string matching.
        For production, integrate BERTScore or embedding-based clustering.

        From framework.md: Reduction from 3.1 to 1.5 bits indicates moving
        from ~8 to ~3 effective choices.
        """
        # Simplified: use output entropy as proxy
        # TODO: Implement proper semantic clustering
        return self.output_entropy

    @property
    def first_divergence_estimate(self) -> int | None:
        """Estimate token position of first divergence.

        Compares outputs character-by-character to find earliest divergence.
        Returns None if all outputs are identical.
        """
        if len(self.outputs) < 2:
            return None

        if self.unique_outputs == 1:
            return None  # All identical

        # Compare first output to all others
        reference = self.outputs[0]
        min_divergence = len(reference)

        for output in self.outputs[1:]:
            for i, (c1, c2) in enumerate(zip(reference, output)):
                if c1 != c2:
                    min_divergence = min(min_divergence, i)
                    break
            else:
                # One is prefix of another
                if len(reference) != len(output):
                    min_divergence = min(min_divergence, min(len(reference), len(output)))

        return min_divergence if min_divergence < len(reference) else None

    @property
    def is_deterministic(self) -> bool:
        """Check if outputs are perfectly deterministic."""
        return self.unique_outputs == 1 and self.sample_size > 0

    @property
    def has_sufficient_samples(self) -> bool:
        """Check if we have enough samples for rigorous testing."""
        return self.sample_size >= self.MIN_SAMPLES_RIGOROUS

    def is_competitive(self) -> bool:
        """Check if metrics meet competitive thresholds."""
        return self.exact_match_rate >= self.EXACT_MATCH_COMPETITIVE

    def is_excellent(self) -> bool:
        """Check if metrics meet excellent thresholds."""
        return self.exact_match_rate >= self.EXACT_MATCH_EXCELLENT

    def to_collector(self, collector: MetricsCollector | None = None) -> MetricsCollector:
        """Export metrics to a collector.

        Args:
            collector: Existing collector to add to, or None to create new

        Returns:
            MetricsCollector with consistency metrics
        """
        collector = collector or MetricsCollector()

        collector.record("sample_size", self.sample_size, "count", "consistency")
        collector.record("unique_outputs", self.unique_outputs, "count", "consistency")
        collector.record("exact_match_rate", self.exact_match_rate, "ratio", "consistency")
        collector.record("output_entropy", self.output_entropy, "bits", "consistency")
        collector.record("semantic_entropy", self.semantic_entropy, "bits", "consistency")
        collector.record("is_deterministic", self.is_deterministic, "bool", "consistency")
        collector.record(
            "has_sufficient_samples", self.has_sufficient_samples, "bool", "consistency"
        )

        divergence = self.first_divergence_estimate
        if divergence is not None:
            collector.record(
                "first_divergence_position", divergence, "chars", "consistency"
            )

        collector.record("is_competitive", self.is_competitive(), "bool", "consistency")
        collector.record("is_excellent", self.is_excellent(), "bool", "consistency")

        return collector


@dataclass
class SchemaComplianceMetrics:
    """Schema conformance metrics from JSONSchemaBench.

    From framework.md:
    - OpenAI structured outputs: 100% in strict mode vs 35% with prompting
    - Claude 3.5 Sonnet: 100% (simple) / 85-95% (complex)
    - GPT-4o: 100% (simple) / 90-100% (complex)
    """

    simple_schema_attempts: int = 0
    simple_schema_passes: int = 0
    complex_schema_attempts: int = 0
    complex_schema_passes: int = 0

    # Thresholds
    SIMPLE_TARGET = 1.0       # 100% for simple schemas
    COMPLEX_COMPETITIVE = 0.85
    COMPLEX_EXCELLENT = 0.95

    def record_simple_schema_result(self, passed: bool) -> None:
        """Record a simple schema validation result."""
        self.simple_schema_attempts += 1
        if passed:
            self.simple_schema_passes += 1

    def record_complex_schema_result(self, passed: bool) -> None:
        """Record a complex schema validation result."""
        self.complex_schema_attempts += 1
        if passed:
            self.complex_schema_passes += 1

    @property
    def simple_compliance_rate(self) -> float:
        """Simple schema compliance rate."""
        if self.simple_schema_attempts == 0:
            return 0.0
        return self.simple_schema_passes / self.simple_schema_attempts

    @property
    def complex_compliance_rate(self) -> float:
        """Complex schema compliance rate."""
        if self.complex_schema_attempts == 0:
            return 0.0
        return self.complex_schema_passes / self.complex_schema_attempts

    def to_collector(self, collector: MetricsCollector | None = None) -> MetricsCollector:
        """Export metrics to a collector."""
        collector = collector or MetricsCollector()

        collector.record(
            "simple_schema_compliance",
            self.simple_compliance_rate,
            "ratio",
            "consistency",
        )
        collector.record(
            "complex_schema_compliance",
            self.complex_compliance_rate,
            "ratio",
            "consistency",
        )
        collector.record(
            "simple_schema_attempts",
            self.simple_schema_attempts,
            "count",
            "consistency",
        )
        collector.record(
            "complex_schema_attempts",
            self.complex_schema_attempts,
            "count",
            "consistency",
        )

        return collector
