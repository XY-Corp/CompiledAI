"""Cost and TCO metrics for compiled vs runtime comparison.

Based on framework.md research including:
- NVIDIA TCO Framework
- Pan & Wang 2025 break-even calculations
- Commercial API pricing (January 2026)
- Prompt caching savings analysis
"""

from dataclasses import dataclass

from .base import MetricsCollector


@dataclass
class APIPricing:
    """API pricing per million tokens (January 2026 from framework.md).

    Usage:
        pricing = APIPricing.CLAUDE_4_SONNET
        cost = (input_tokens * pricing.input + output_tokens * pricing.output) / 1_000_000
    """

    input: float   # $/1M input tokens
    output: float  # $/1M output tokens
    name: str = ""

    # Predefined pricing from framework.md
    @classmethod
    @property
    def GPT_4O(cls) -> "APIPricing":
        return cls(input=2.50, output=10.00, name="GPT-4o")

    @classmethod
    @property
    def CLAUDE_4_SONNET(cls) -> "APIPricing":
        return cls(input=3.00, output=15.00, name="Claude 4 Sonnet")

    @classmethod
    @property
    def GEMINI_25_PRO(cls) -> "APIPricing":
        return cls(input=1.25, output=10.00, name="Gemini 2.5 Pro")


@dataclass
class CostMetrics:
    """TCO metrics from NVIDIA framework and academic literature.

    From framework.md:
    - Break-even for small models (24-32B): 0.3-3 months at >50M tokens/month
    - Break-even for medium models (70-120B): 2.3-34 months
    - Cache hit reduces costs by 81-90%
    - LLM inference declining 10x per year

    Attributes:
        generation_input_tokens: Input tokens for code generation
        generation_output_tokens: Output tokens for code generation
        runtime_tokens_per_tx: Runtime tokens per transaction
        pricing: API pricing to use for cost calculations
        n_executions: Number of expected/actual executions
    """

    generation_input_tokens: int = 0
    generation_output_tokens: int = 0
    runtime_tokens_per_tx: float = 0.0

    pricing: APIPricing | None = None

    # Execution tracking
    n_executions: int = 0

    # Cache metrics
    cache_hits: int = 0
    cache_misses: int = 0

    # Infrastructure costs (yearly, USD)
    hardware_cost_yearly: float = 0.0
    software_cost_yearly: float = 0.0
    hosting_cost_yearly: float = 0.0

    # Thresholds from framework.md
    BREAK_EVEN_COMPETITIVE = 100    # <100 executions is competitive
    BREAK_EVEN_EXCELLENT = 10       # <10 executions is excellent
    CACHE_SAVINGS_MIN = 0.81        # 81% minimum cache savings
    CACHE_SAVINGS_MAX = 0.90        # 90% maximum cache savings

    @property
    def generation_cost_usd(self) -> float:
        """One-time generation cost in USD."""
        if not self.pricing:
            return 0.0
        return (
            self.generation_input_tokens * self.pricing.input
            + self.generation_output_tokens * self.pricing.output
        ) / 1_000_000

    @property
    def runtime_cost_per_tx_usd(self) -> float:
        """Runtime cost per transaction in USD.

        For compiled AI, this should be ~0 (no LLM calls at runtime).
        """
        if not self.pricing or self.runtime_tokens_per_tx == 0:
            return 0.0
        # Assume roughly 50/50 input/output split for runtime
        avg_price = (self.pricing.input + self.pricing.output) / 2
        return (self.runtime_tokens_per_tx * avg_price) / 1_000_000

    def total_cost_at_n(self, n: int) -> float:
        """Total cost for n executions.

        Args:
            n: Number of executions

        Returns:
            Total cost = generation_cost + runtime_cost * n
        """
        return self.generation_cost_usd + (self.runtime_cost_per_tx_usd * n)

    def cost_per_tx_at_n(self, n: int) -> float:
        """Cost per transaction at n executions.

        Formula: (GenCost/n) + RuntimeCostPerTx + InfraCostPerTx
        """
        if n == 0:
            return float("inf")
        amortized_gen = self.generation_cost_usd / n
        # Include infrastructure if available (per-tx share)
        infra_per_tx = self.infrastructure_cost_per_tx(n)
        return amortized_gen + self.runtime_cost_per_tx_usd + infra_per_tx

    def infrastructure_cost_per_tx(self, n_per_year: int) -> float:
        """Infrastructure cost per transaction.

        Args:
            n_per_year: Number of transactions per year

        Returns:
            Infrastructure cost per transaction
        """
        if n_per_year == 0:
            return 0.0
        total_infra = (
            self.hardware_cost_yearly
            + self.software_cost_yearly
            + self.hosting_cost_yearly
        )
        return total_infra / n_per_year

    def break_even_executions(self, runtime_cost_per_tx: float) -> int:
        """Calculate break-even point vs runtime baseline.

        From Pan & Wang 2025 framework:
        n* = Generation_Cost / Runtime_Cost_Per_Execution

        Args:
            runtime_cost_per_tx: Runtime inference cost per transaction

        Returns:
            Number of executions for break-even
        """
        if runtime_cost_per_tx <= self.runtime_cost_per_tx_usd:
            return -1  # Never breaks even (runtime is same or cheaper)
        cost_savings_per_tx = runtime_cost_per_tx - self.runtime_cost_per_tx_usd
        return int(self.generation_cost_usd / cost_savings_per_tx) + 1

    def determinism_advantage(self, runtime_cost_per_tx: float, n: int) -> float:
        """Calculate Determinism Advantage ratio.

        DA = Runtime_Inference_Cost × N_executions / Generation_Cost

        When DA > 1, compiled approach is more efficient.
        For deterministic code with near-zero runtime cost, DA → ∞.

        Args:
            runtime_cost_per_tx: Runtime inference cost per transaction
            n: Number of executions

        Returns:
            Determinism advantage ratio
        """
        if self.generation_cost_usd == 0:
            return float("inf")
        return (runtime_cost_per_tx * n) / self.generation_cost_usd

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total

    @property
    def cache_savings_estimate(self) -> float:
        """Estimated savings from caching.

        From framework.md: Cache hit reduces costs by 81-90%.
        """
        if self.cache_hit_rate == 0:
            return 0.0
        # Use midpoint of savings range
        savings_rate = (self.CACHE_SAVINGS_MIN + self.CACHE_SAVINGS_MAX) / 2
        return self.cache_hit_rate * savings_rate

    def is_break_even_competitive(self, runtime_cost_per_tx: float) -> bool:
        """Check if break-even is competitive (<100 executions)."""
        be = self.break_even_executions(runtime_cost_per_tx)
        return 0 < be <= self.BREAK_EVEN_COMPETITIVE

    def is_break_even_excellent(self, runtime_cost_per_tx: float) -> bool:
        """Check if break-even is excellent (<10 executions)."""
        be = self.break_even_executions(runtime_cost_per_tx)
        return 0 < be <= self.BREAK_EVEN_EXCELLENT

    def to_collector(
        self,
        runtime_cost_per_tx: float = 0.0,
        n_values: list[int] | None = None,
        collector: MetricsCollector | None = None,
    ) -> MetricsCollector:
        """Export metrics to a collector.

        Args:
            runtime_cost_per_tx: Runtime baseline cost for comparison
            n_values: Transaction counts to calculate costs for
            collector: Existing collector to add to, or None to create new

        Returns:
            MetricsCollector with cost metrics
        """
        collector = collector or MetricsCollector()
        n_values = n_values or [100, 1000, 10000, 100000, 1000000]

        # Generation costs
        collector.record(
            "generation_input_tokens",
            self.generation_input_tokens,
            "tokens",
            "cost",
        )
        collector.record(
            "generation_output_tokens",
            self.generation_output_tokens,
            "tokens",
            "cost",
        )
        collector.record("generation_cost_usd", self.generation_cost_usd, "usd", "cost")

        # Runtime costs
        collector.record(
            "runtime_tokens_per_tx", self.runtime_tokens_per_tx, "tokens", "cost"
        )
        collector.record(
            "runtime_cost_per_tx_usd", self.runtime_cost_per_tx_usd, "usd", "cost"
        )

        # Cost at various N
        for n in n_values:
            collector.record(f"total_cost_at_{n}", self.total_cost_at_n(n), "usd", "cost")
            collector.record(f"cost_per_tx_at_{n}", self.cost_per_tx_at_n(n), "usd", "cost")

        # Break-even analysis
        if runtime_cost_per_tx > 0:
            be = self.break_even_executions(runtime_cost_per_tx)
            collector.record("break_even_executions", be, "count", "cost")

            for n in n_values:
                da = self.determinism_advantage(runtime_cost_per_tx, n)
                collector.record(f"determinism_advantage_at_{n}", da, "ratio", "cost")

            collector.record(
                "is_break_even_competitive",
                self.is_break_even_competitive(runtime_cost_per_tx),
                "bool",
                "cost",
            )
            collector.record(
                "is_break_even_excellent",
                self.is_break_even_excellent(runtime_cost_per_tx),
                "bool",
                "cost",
            )

        # Cache metrics
        collector.record("cache_hit_rate", self.cache_hit_rate, "ratio", "cost")
        collector.record(
            "cache_savings_estimate", self.cache_savings_estimate, "ratio", "cost"
        )

        # Infrastructure
        collector.record(
            "hardware_cost_yearly", self.hardware_cost_yearly, "usd", "cost"
        )
        collector.record(
            "software_cost_yearly", self.software_cost_yearly, "usd", "cost"
        )
        collector.record(
            "hosting_cost_yearly", self.hosting_cost_yearly, "usd", "cost"
        )

        return collector


def calculate_tco(
    generation_cost: float,
    runtime_cost_per_tx: float,
    n_per_month: int,
    months: int,
    infrastructure_monthly: float = 0.0,
) -> float:
    """Calculate Total Cost of Ownership.

    Args:
        generation_cost: One-time generation cost
        runtime_cost_per_tx: Runtime cost per transaction
        n_per_month: Transactions per month
        months: Number of months
        infrastructure_monthly: Monthly infrastructure cost

    Returns:
        Total cost over the period
    """
    total_transactions = n_per_month * months
    return (
        generation_cost
        + (runtime_cost_per_tx * total_transactions)
        + (infrastructure_monthly * months)
    )
