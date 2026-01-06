"""Token efficiency metrics for compiled vs runtime comparison."""

from dataclasses import dataclass, field
from typing import Callable

from .base import MetricsCollector


@dataclass
class TokenMetrics:
    """Token efficiency metrics for a workflow.

    Based on framework.md research including LLMLingua compression ratios,
    Pan & Wang 2025 break-even framework, and ENAMEL efficiency benchmarks.

    Attributes:
        gen_tokens: Tokens consumed during code generation (one-time cost)
        runtime_tokens_per_tx: Tokens consumed per transaction at runtime
        prompt_tokens: Total prompt tokens used in generation
        generated_loc: Lines of code generated
        output_code_tokens: Tokens in the generated code output
        expected_executions: Expected number of workflow executions
    """

    gen_tokens: int = 0
    runtime_tokens_per_tx: float = 0.0
    prompt_tokens: int = 0
    generated_loc: int = 0
    output_code_tokens: int = 0
    expected_executions: int = 1000  # Default expected executions for amortization

    # Track individual transaction token counts for variance analysis
    runtime_token_samples: list[int] = field(default_factory=list)

    # Competitive thresholds from framework.md
    COMPRESSION_RATIO_COMPETITIVE = 4.0  # >4x is competitive
    COMPRESSION_RATIO_EXCELLENT = 10.0   # >10x is excellent
    BREAK_EVEN_COMPETITIVE = 100         # <100 executions is competitive
    BREAK_EVEN_EXCELLENT = 10            # <10 executions is excellent

    def total_tokens(self, n: int) -> float:
        """Calculate total tokens for n transactions.

        Args:
            n: Number of transactions

        Returns:
            Total tokens = gen_tokens + runtime_tokens_per_tx * n
        """
        return self.gen_tokens + (self.runtime_tokens_per_tx * n)

    def total_tokens_fn(self) -> Callable[[int], float]:
        """Return a function f(n) = total tokens for n transactions."""
        gen = self.gen_tokens
        per_tx = self.runtime_tokens_per_tx
        return lambda n: gen + (per_tx * n)

    @property
    def break_even_n(self) -> int | None:
        """Calculate break-even point vs a runtime baseline.

        This is calculated during comparison, not standalone.
        Returns None for standalone metrics.
        """
        return None

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio: Output Code Tokens / Input Prompt Tokens.

        From framework.md: LLMLingua achieves up to 20x compression with minimal loss.
        Higher ratio means better compression (more code per prompt token).
        Target: >4x competitive, >10x excellent.
        """
        if self.prompt_tokens == 0:
            return 0.0
        return self.output_code_tokens / self.prompt_tokens

    @property
    def loc_per_token(self) -> float:
        """Lines of Code Generated / Total Tokens Consumed.

        Measures efficiency of code generation.
        Higher is better.
        """
        if self.gen_tokens == 0:
            return 0.0
        return self.generated_loc / self.gen_tokens

    @property
    def token_amortization_factor(self) -> float:
        """Generation_Tokens / Expected_Executions.

        From framework.md: Measures how well generation cost amortizes.
        Lower is better (less tokens per expected execution).
        """
        if self.expected_executions == 0:
            return float("inf")
        return self.gen_tokens / self.expected_executions

    def determinism_advantage(self, runtime_cost_per_tx: float, n_executions: int) -> float:
        """Calculate Determinism Advantage: Runtime_Cost × N / Generation_Cost.

        From framework.md: When DA > 1, compiled approach is more efficient.
        For deterministic code with near-zero runtime cost, DA → ∞ after break-even.

        Args:
            runtime_cost_per_tx: Runtime inference cost per transaction (tokens or $)
            n_executions: Number of executions

        Returns:
            Determinism advantage ratio. >1 means compiled is better.
        """
        if self.gen_tokens == 0:
            return float("inf")
        return (runtime_cost_per_tx * n_executions) / self.gen_tokens

    def is_competitive(self) -> bool:
        """Check if metrics meet competitive thresholds."""
        return self.compression_ratio >= self.COMPRESSION_RATIO_COMPETITIVE

    def is_excellent(self) -> bool:
        """Check if metrics meet excellent thresholds."""
        return self.compression_ratio >= self.COMPRESSION_RATIO_EXCELLENT

    def record_generation(self, input_tokens: int, output_tokens: int, loc: int) -> None:
        """Record a code generation event.

        Args:
            input_tokens: Prompt tokens used
            output_tokens: Generated tokens (code tokens)
            loc: Lines of code generated
        """
        self.prompt_tokens += input_tokens
        self.output_code_tokens += output_tokens
        self.gen_tokens += input_tokens + output_tokens
        self.generated_loc += loc

    def record_runtime_tx(self, tokens: int) -> None:
        """Record tokens used for a runtime transaction.

        Args:
            tokens: Total tokens for this transaction
        """
        self.runtime_token_samples.append(tokens)
        # Update running average
        self.runtime_tokens_per_tx = sum(self.runtime_token_samples) / len(
            self.runtime_token_samples
        )

    def to_collector(self, collector: MetricsCollector | None = None) -> MetricsCollector:
        """Export metrics to a collector.

        Args:
            collector: Existing collector to add to, or None to create new

        Returns:
            MetricsCollector with token metrics
        """
        collector = collector or MetricsCollector()

        # Core token counts
        collector.record("gen_tokens", self.gen_tokens, "tokens", "token_efficiency")
        collector.record("prompt_tokens", self.prompt_tokens, "tokens", "token_efficiency")
        collector.record("output_code_tokens", self.output_code_tokens, "tokens", "token_efficiency")
        collector.record(
            "runtime_tokens_per_tx",
            self.runtime_tokens_per_tx,
            "tokens/tx",
            "token_efficiency",
        )

        # Code metrics
        collector.record("generated_loc", self.generated_loc, "lines", "token_efficiency")

        # Efficiency ratios (from framework.md)
        collector.record(
            "compression_ratio", self.compression_ratio, "ratio", "token_efficiency"
        )
        collector.record("loc_per_token", self.loc_per_token, "loc/token", "token_efficiency")
        collector.record(
            "token_amortization_factor",
            self.token_amortization_factor,
            "tokens/exec",
            "token_efficiency",
        )

        # Thresholds
        collector.record("is_competitive", self.is_competitive(), "bool", "token_efficiency")
        collector.record("is_excellent", self.is_excellent(), "bool", "token_efficiency")

        return collector


@dataclass
class TokenComparison:
    """Compare token efficiency between compiled and runtime approaches."""

    compiled: TokenMetrics
    runtime: TokenMetrics

    def break_even_n(self) -> int:
        """Calculate break-even point where compiled becomes cheaper.

        Returns:
            Number of transactions where compiled total tokens < runtime total tokens
            Returns 0 if compiled is always cheaper (runtime_tokens_per_tx <= compiled)
            Returns -1 if compiled is never cheaper (shouldn't happen in practice)
        """
        # compiled_total = gen_tokens + compiled_runtime_per_tx * n
        # runtime_total = runtime_tokens_per_tx * n
        # Break-even: gen_tokens + compiled_runtime_per_tx * n = runtime_tokens_per_tx * n
        # gen_tokens = (runtime_tokens_per_tx - compiled_runtime_per_tx) * n
        # n = gen_tokens / (runtime_tokens_per_tx - compiled_runtime_per_tx)

        delta_per_tx = self.runtime.runtime_tokens_per_tx - self.compiled.runtime_tokens_per_tx

        if delta_per_tx <= 0:
            # Runtime is cheaper or equal per transaction
            return -1

        return int(self.compiled.gen_tokens / delta_per_tx) + 1

    def savings_at_n(self, n: int) -> float:
        """Calculate token savings at n transactions.

        Args:
            n: Number of transactions

        Returns:
            Tokens saved (positive) or extra tokens used (negative)
        """
        return self.runtime.total_tokens(n) - self.compiled.total_tokens(n)

    def savings_ratio_at_n(self, n: int) -> float:
        """Calculate savings ratio at n transactions.

        Args:
            n: Number of transactions

        Returns:
            Ratio of compiled/runtime tokens (< 1 means compiled is cheaper)
        """
        runtime_total = self.runtime.total_tokens(n)
        if runtime_total == 0:
            return 0.0
        return self.compiled.total_tokens(n) / runtime_total

    def to_collector(
        self, n_values: list[int] | None = None, collector: MetricsCollector | None = None
    ) -> MetricsCollector:
        """Export comparison metrics to a collector.

        Args:
            n_values: Transaction counts to calculate metrics for
            collector: Existing collector to add to, or None to create new

        Returns:
            MetricsCollector with comparison metrics
        """
        collector = collector or MetricsCollector()
        n_values = n_values or [100, 1000, 10000, 100000]

        collector.record("break_even_n", self.break_even_n(), "transactions", "token_efficiency")

        for n in n_values:
            collector.record(
                f"compiled_total_tokens_at_{n}",
                self.compiled.total_tokens(n),
                "tokens",
                "token_efficiency",
            )
            collector.record(
                f"runtime_total_tokens_at_{n}",
                self.runtime.total_tokens(n),
                "tokens",
                "token_efficiency",
            )
            collector.record(
                f"savings_at_{n}",
                self.savings_at_n(n),
                "tokens",
                "token_efficiency",
            )
            collector.record(
                f"savings_ratio_at_{n}",
                self.savings_ratio_at_n(n),
                "ratio",
                "token_efficiency",
            )

        return collector
