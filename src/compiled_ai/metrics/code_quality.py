"""Code quality metrics for generated code evaluation.

Based on framework.md research including:
- Cyclomatic and cognitive complexity (SonarQube)
- Maintainability Index
- Security scanning (Bandit, Semgrep)
- Test coverage targets
- pass@k code generation metrics
"""

from dataclasses import dataclass, field

from .base import MetricsCollector


@dataclass
class CodeQualityMetrics:
    """Code quality metrics from software engineering standards.

    From framework.md:
    - Cyclomatic complexity target: <10/method, excellent: <5
    - Cognitive complexity target: <15/function
    - Maintainability Index target: >65, excellent: >85
    - Line coverage target: ≥80%
    - pass@1 SOTA: >90% on HumanEval
    """

    # Complexity metrics
    cyclomatic_complexity: float = 0.0
    cognitive_complexity: float = 0.0
    halstead_volume: float = 0.0
    maintainability_index: float = 0.0

    # Technical debt
    technical_debt_ratio: float = 0.0  # Remediation_Cost / Development_Cost

    # Security metrics
    critical_vulnerabilities: int = 0
    high_vulnerabilities: int = 0
    medium_vulnerabilities: int = 0
    low_vulnerabilities: int = 0

    # Coverage metrics
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    mutation_score: float = 0.0

    # Code generation benchmarks
    pass_at_1: float = 0.0
    pass_at_k: float = 0.0  # For k > 1

    # Lines of code metrics
    total_loc: int = 0
    code_loc: int = 0  # Excluding comments/blanks

    # Thresholds from framework.md
    CYCLOMATIC_TARGET = 10.0
    CYCLOMATIC_EXCELLENT = 5.0
    COGNITIVE_TARGET = 15.0
    MAINTAINABILITY_TARGET = 65.0
    MAINTAINABILITY_EXCELLENT = 85.0
    TECH_DEBT_TARGET = 0.05  # <5%
    LINE_COVERAGE_TARGET = 0.80
    BRANCH_COVERAGE_TARGET = 0.75
    MUTATION_SCORE_TARGET = 0.70
    PASS_AT_1_COMPETITIVE = 0.80
    PASS_AT_1_EXCELLENT = 0.90

    @property
    def total_vulnerabilities(self) -> int:
        """Total count of security vulnerabilities."""
        return (
            self.critical_vulnerabilities
            + self.high_vulnerabilities
            + self.medium_vulnerabilities
            + self.low_vulnerabilities
        )

    @property
    def has_critical_security_issues(self) -> bool:
        """Check for critical/high severity security issues."""
        return self.critical_vulnerabilities > 0 or self.high_vulnerabilities > 0

    @property
    def security_rating(self) -> str:
        """SonarQube-style security rating A-E.

        A: 0 vulnerabilities
        B: At least 1 minor
        C: At least 1 major
        D: At least 1 critical
        E: At least 1 blocker
        """
        if self.total_vulnerabilities == 0:
            return "A"
        elif self.critical_vulnerabilities > 0:
            return "D"
        elif self.high_vulnerabilities > 0:
            return "C"
        elif self.medium_vulnerabilities > 0:
            return "B"
        return "B"  # Low only

    def meets_complexity_targets(self) -> bool:
        """Check if complexity metrics meet targets."""
        return (
            self.cyclomatic_complexity <= self.CYCLOMATIC_TARGET
            and self.cognitive_complexity <= self.COGNITIVE_TARGET
        )

    def meets_coverage_targets(self) -> bool:
        """Check if coverage metrics meet targets."""
        return (
            self.line_coverage >= self.LINE_COVERAGE_TARGET
            and self.branch_coverage >= self.BRANCH_COVERAGE_TARGET
        )

    def meets_quality_gate(self) -> bool:
        """Check if code passes quality gate (all targets met)."""
        return (
            self.meets_complexity_targets()
            and self.meets_coverage_targets()
            and not self.has_critical_security_issues
            and self.maintainability_index >= self.MAINTAINABILITY_TARGET
            and self.technical_debt_ratio <= self.TECH_DEBT_TARGET
        )

    def is_competitive(self) -> bool:
        """Check if code generation is competitive (pass@1 >= 80%)."""
        return self.pass_at_1 >= self.PASS_AT_1_COMPETITIVE

    def is_excellent(self) -> bool:
        """Check if code generation is excellent (pass@1 >= 90%)."""
        return self.pass_at_1 >= self.PASS_AT_1_EXCELLENT

    def to_collector(self, collector: MetricsCollector | None = None) -> MetricsCollector:
        """Export metrics to a collector.

        Args:
            collector: Existing collector to add to, or None to create new

        Returns:
            MetricsCollector with code quality metrics
        """
        collector = collector or MetricsCollector()

        # Complexity
        collector.record(
            "cyclomatic_complexity", self.cyclomatic_complexity, "score", "code_quality"
        )
        collector.record(
            "cognitive_complexity", self.cognitive_complexity, "score", "code_quality"
        )
        collector.record("halstead_volume", self.halstead_volume, "score", "code_quality")
        collector.record(
            "maintainability_index", self.maintainability_index, "score", "code_quality"
        )

        # Technical debt
        collector.record(
            "technical_debt_ratio", self.technical_debt_ratio, "ratio", "code_quality"
        )

        # Security
        collector.record(
            "critical_vulnerabilities", self.critical_vulnerabilities, "count", "code_quality"
        )
        collector.record(
            "high_vulnerabilities", self.high_vulnerabilities, "count", "code_quality"
        )
        collector.record(
            "medium_vulnerabilities", self.medium_vulnerabilities, "count", "code_quality"
        )
        collector.record(
            "low_vulnerabilities", self.low_vulnerabilities, "count", "code_quality"
        )
        collector.record(
            "total_vulnerabilities", self.total_vulnerabilities, "count", "code_quality"
        )
        collector.record("security_rating", self.security_rating, "grade", "code_quality")

        # Coverage
        collector.record("line_coverage", self.line_coverage, "ratio", "code_quality")
        collector.record("branch_coverage", self.branch_coverage, "ratio", "code_quality")
        collector.record("mutation_score", self.mutation_score, "ratio", "code_quality")

        # Code generation
        collector.record("pass_at_1", self.pass_at_1, "ratio", "code_quality")
        collector.record("pass_at_k", self.pass_at_k, "ratio", "code_quality")

        # LOC
        collector.record("total_loc", self.total_loc, "lines", "code_quality")
        collector.record("code_loc", self.code_loc, "lines", "code_quality")

        # Quality gate
        collector.record(
            "meets_complexity_targets", self.meets_complexity_targets(), "bool", "code_quality"
        )
        collector.record(
            "meets_coverage_targets", self.meets_coverage_targets(), "bool", "code_quality"
        )
        collector.record(
            "meets_quality_gate", self.meets_quality_gate(), "bool", "code_quality"
        )
        collector.record("is_competitive", self.is_competitive(), "bool", "code_quality")
        collector.record("is_excellent", self.is_excellent(), "bool", "code_quality")

        return collector


def calculate_pass_at_k(n: int, c: int, k: int) -> float:
    """Calculate pass@k metric for code generation.

    pass@k = 1 - C(n-c,k)/C(n,k)

    From framework.md: Primary code generation metric.
    Current SOTA: HumanEval >90% pass@1 for frontier models.

    Args:
        n: Total number of samples generated
        c: Number of correct samples
        k: Number of samples to consider

    Returns:
        pass@k probability
    """
    if n - c < k:
        return 1.0
    # Use logarithms to avoid overflow with large numbers
    import math

    def log_comb(n: int, k: int) -> float:
        if k > n or k < 0:
            return float("-inf")
        if k == 0 or k == n:
            return 0.0
        return sum(math.log(n - i) - math.log(i + 1) for i in range(k))

    log_numerator = log_comb(n - c, k)
    log_denominator = log_comb(n, k)

    if log_numerator == float("-inf"):
        return 1.0

    return 1.0 - math.exp(log_numerator - log_denominator)
