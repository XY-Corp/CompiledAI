"""Direct LLM Baseline: Per-transaction prompting with no compilation."""

import time
from typing import Any

from .base import BaseBaseline, BaselineResult, TaskInput, register_baseline
from ..utils.llm_client import LLMConfig, TokenTracker, create_client


@register_baseline("direct_llm")
class DirectLLMBaseline(BaseBaseline):
    """Direct LLM baseline - calls LLM for every task execution.

    This serves as the comparison point for Compiled AI:
    - No code generation phase
    - Full LLM inference per transaction
    - Higher token costs at scale
    - Non-deterministic outputs
    """

    description = "Per-transaction LLM inference (no compilation)"

    def __init__(
        self,
        provider: str = "anthropic",
        model: str | None = None,
        system_prompt: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        enable_cache: bool = False,
        verbose: bool = False,
    ) -> None:
        """Initialize the Direct LLM baseline.

        Args:
            provider: LLM provider ("anthropic", "openai", or "gemini")
            model: Model name. Defaults to provider's default model.
            system_prompt: Optional system prompt to use
            max_retries: Maximum retry attempts on failure
            retry_delay: Base delay between retries (exponential backoff)
            enable_cache: Whether to cache LLM responses
            verbose: Enable verbose logging (currently unused)
        """
        self.provider = provider
        self.verbose = verbose
        self.config = LLMConfig(
            model=model or self._default_model(provider),
            system_prompt=system_prompt,
        )
        self.client = create_client(
            provider, config=self.config, enable_cache=enable_cache
        )
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.token_tracker = TokenTracker()

    def _default_model(self, provider: str) -> str:
        """Get default model for provider.

        Args:
            provider: LLM provider name

        Returns:
            Default model name for the provider
        """
        defaults = {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4o",
            "gemini": "gemini-2.0-flash",
        }
        return defaults.get(provider, "claude-sonnet-4-20250514")

    def run(self, task_input: TaskInput) -> BaselineResult:
        """Execute LLM inference for a single task.

        Args:
            task_input: Task input with prompt and context

        Returns:
            BaselineResult with output and metrics
        """
        start_time = time.perf_counter()

        # Build prompt with context
        prompt = task_input.prompt
        if task_input.context:
            context_str = "\n".join(
                f"{k}: {v}" for k, v in task_input.context.items()
            )
            prompt = f"Context:\n{context_str}\n\nTask:\n{prompt}"

        # Retry logic with exponential backoff
        last_error: str | None = None
        responses = []

        for attempt in range(self.max_retries):
            try:
                response = self.client.generate(prompt)
                responses.append(response)
                self.token_tracker.record(response)

                latency_ms = (time.perf_counter() - start_time) * 1000

                return BaselineResult(
                    task_id=task_input.task_id,
                    output=response.content,
                    success=True,
                    latency_ms=latency_ms,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    llm_calls=attempt + 1,
                    responses=responses,
                )
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2**attempt))  # Exponential backoff

        latency_ms = (time.perf_counter() - start_time) * 1000
        return BaselineResult(
            task_id=task_input.task_id,
            output="",
            success=False,
            error=last_error,
            latency_ms=latency_ms,
            llm_calls=self.max_retries,
            responses=responses,
        )

    def get_token_summary(self) -> dict[str, Any]:
        """Get cumulative token usage summary.

        Returns:
            Dictionary with token usage statistics
        """
        return {
            "total_input_tokens": self.token_tracker.input_tokens,
            "total_output_tokens": self.token_tracker.output_tokens,
            "total_tokens": self.token_tracker.total_tokens,
            "total_calls": self.token_tracker.calls,
            "cached_calls": self.token_tracker.cached_calls,
            "avg_latency_ms": self.token_tracker.avg_latency_ms,
        }
