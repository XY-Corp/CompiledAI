"""Adapter for PydanticAI model configuration and metrics tracking.

This module bridges the Code Factory with PydanticAI's model support,
providing consistent configuration and metrics collection.
"""

from dataclasses import dataclass, field
from typing import Literal

# PydanticAI model imports
from pydantic_ai.settings import ModelSettings
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.gemini import GeminiModel


ProviderType = Literal["anthropic", "openai", "gemini"]


DEFAULT_MODELS: dict[ProviderType, str] = {
    "anthropic": "claude-opus-4-5-20251101",  # Opus 4.5 with extended thinking support
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
}


@dataclass
class AdapterMetrics:
    """Metrics collected during agent execution."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_calls: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    def record(
        self,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float = 0.0,
    ) -> None:
        """Record metrics from an agent call."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_calls += 1
        if latency_ms > 0:
            self.latencies_ms.append(latency_ms)

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def avg_latency_ms(self) -> float:
        """Average latency across calls."""
        if not self.latencies_ms:
            return 0.0
        return sum(self.latencies_ms) / len(self.latencies_ms)

    def reset(self) -> None:
        """Reset all metrics."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0
        self.latencies_ms = []


def create_model(
    provider: ProviderType = "anthropic",
    model: str | None = None,
    enable_thinking: bool = False,  # Disabled: incompatible with structured outputs
    thinking_budget_tokens: int = 8000,
) -> AnthropicModel | OpenAIModel | GeminiModel:
    """Create a PydanticAI model for the specified provider.

    Args:
        provider: LLM provider ("anthropic", "openai", or "gemini")
        model: Specific model name, or None for provider default
        enable_thinking: Extended thinking (disabled - incompatible with structured outputs)
        thinking_budget_tokens: Token budget for extended thinking (unused)

    Returns:
        Configured PydanticAI model instance

    Note:
        Extended thinking cannot be used with PydanticAI's structured outputs
        because tool_choice is forced, which conflicts with thinking mode.
        Code Factory requires structured outputs (WorkflowSpec, GeneratedFiles),
        so extended thinking is disabled.
    """
    model_name = model or DEFAULT_MODELS.get(provider, DEFAULT_MODELS["anthropic"])

    if provider == "anthropic":
        # Note: Extended thinking is disabled because it's incompatible with
        # structured outputs (tool_choice forced). Code Factory needs structured
        # outputs for WorkflowSpec and GeneratedFiles Pydantic models.
        return AnthropicModel(model_name)
    elif provider == "openai":
        return OpenAIModel(model_name)
    elif provider == "gemini":
        return GeminiModel(model_name)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def extract_usage_from_result(result) -> tuple[int, int]:
    """Extract token usage from a PydanticAI agent result.

    Args:
        result: Result from agent.run()

    Returns:
        Tuple of (input_tokens, output_tokens)
    """
    input_tokens = 0
    output_tokens = 0

    # PydanticAI stores usage in result.usage()
    try:
        usage = result.usage()
        input_tokens = usage.request_tokens or 0
        output_tokens = usage.response_tokens or 0
    except (AttributeError, TypeError):
        # Fallback if usage not available
        pass

    return input_tokens, output_tokens
