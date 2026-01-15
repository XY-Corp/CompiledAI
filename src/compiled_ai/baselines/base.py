"""Base classes for baseline implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..metrics import LatencyMetrics, MetricsCollector, TokenMetrics
from ..utils.llm_client import LLMResponse


@dataclass
class TaskInput:
    """Input for a benchmark task."""

    task_id: str
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskOutput:
    """Expected output for comparison."""

    content: str
    schema: dict[str, Any] | None = None  # JSON schema for validation
    alternatives: list[str] = field(default_factory=list)  # Acceptable alternatives


@dataclass
class BaselineResult:
    """Result from running a baseline on a single task."""

    task_id: str
    output: str
    success: bool
    error: str | None = None

    # Metrics
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0

    # Response tracking
    responses: list[LLMResponse] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.input_tokens + self.output_tokens


class BaseBaseline(ABC):
    """Abstract base class for all baselines."""

    name: str = "base"
    description: str = "Base baseline"

    @abstractmethod
    def run(self, task_input: TaskInput) -> BaselineResult:
        """Execute the baseline on a single task input.

        Args:
            task_input: The task input to process

        Returns:
            BaselineResult with output and metrics
        """
        ...

    def run_batch(self, inputs: list[TaskInput]) -> list[BaselineResult]:
        """Run baseline on multiple inputs. Override for parallel execution.

        Args:
            inputs: List of task inputs to process

        Returns:
            List of results for each input
        """
        return [self.run(inp) for inp in inputs]

    def to_metrics_collector(self, results: list[BaselineResult]) -> MetricsCollector:
        """Convert results to metrics collector.

        Args:
            results: List of baseline results to aggregate

        Returns:
            MetricsCollector with aggregated metrics
        """
        collector = MetricsCollector()

        # Aggregate latencies
        latencies = [r.latency_ms for r in results if r.success]
        if latencies:
            latency_metrics = LatencyMetrics(measurements=latencies)
            latency_metrics.to_collector(collector)

        # Token usage
        total_input = sum(r.input_tokens for r in results)
        total_output = sum(r.output_tokens for r in results)
        token_metrics = TokenMetrics(
            gen_tokens=total_input + total_output,
            runtime_tokens_per_tx=(total_input + total_output) / len(results)
            if results
            else 0,
        )
        token_metrics.to_collector(collector)

        # Success rate
        success_count = sum(1 for r in results if r.success)
        collector.record(
            "success_rate",
            success_count / len(results) if results else 0,
            "ratio",
            "reliability",
        )
        collector.record(
            "total_llm_calls", sum(r.llm_calls for r in results), "count", "cost"
        )

        return collector


# Registry for baselines
_BASELINE_REGISTRY: dict[str, type[BaseBaseline]] = {}


def register_baseline(name: str):
    """Decorator to register a baseline implementation.

    Args:
        name: Unique name for the baseline

    Returns:
        Decorator that registers the baseline class
    """

    def decorator(cls: type[BaseBaseline]) -> type[BaseBaseline]:
        _BASELINE_REGISTRY[name] = cls
        cls.name = name
        return cls

    return decorator


def get_baseline(name: str, **kwargs: Any) -> BaseBaseline:
    """Get a baseline by name.

    Args:
        name: Name of the baseline to retrieve
        **kwargs: Arguments to pass to the baseline constructor

    Returns:
        Instantiated baseline

    Raises:
        ValueError: If baseline name is not registered
    """
    if name not in _BASELINE_REGISTRY:
        available = list(_BASELINE_REGISTRY.keys())
        raise ValueError(f"Unknown baseline: {name}. Available: {available}")
    return _BASELINE_REGISTRY[name](**kwargs)


def list_baselines() -> list[str]:
    """List all registered baselines.

    Returns:
        List of registered baseline names
    """
    return list(_BASELINE_REGISTRY.keys())
