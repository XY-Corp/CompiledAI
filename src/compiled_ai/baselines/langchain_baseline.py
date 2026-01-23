"""LangChain Baseline: Standard LangChain usage for comparison."""

import os
import time
from typing import Any

from dotenv import load_dotenv

from .base import BaseBaseline, BaselineResult, TaskInput, register_baseline

load_dotenv()


@register_baseline("langchain")
class LangChainBaseline(BaseBaseline):
    """LangChain baseline - standard LangChain invoke.

    Fair comparison showing LangChain framework overhead vs raw API calls.
    Uses same approach as DirectLLM but through LangChain abstractions.
    """

    description = "LangChain standard invoke"

    def __init__(
        self,
        provider: str = "anthropic",
        model: str | None = None,
        system_prompt: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        enable_cache: bool = False,
    ) -> None:
        self.provider = provider
        self.model = model or self._default_model(provider)
        self.system_prompt = system_prompt
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._llm = None

    def _default_model(self, provider: str) -> str:
        defaults = {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4o",
        }
        return defaults.get(provider, "claude-sonnet-4-20250514")

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm

    def _create_llm(self) -> Any:
        if self.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            return ChatAnthropic(
                model=self.model,
                temperature=0,
                anthropic_api_key=api_key,
            )
        elif self.provider == "openai":
            from langchain_openai import ChatOpenAI

            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            return ChatOpenAI(
                model=self.model,
                temperature=0,
                openai_api_key=api_key,
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def run(self, task_input: TaskInput) -> BaselineResult:
        from langchain_core.messages import HumanMessage, SystemMessage

        start_time = time.perf_counter()

        # Build prompt (same as DirectLLM)
        prompt = task_input.prompt
        if task_input.context:
            context_str = "\n".join(f"{k}: {v}" for k, v in task_input.context.items())
            prompt = f"Context:\n{context_str}\n\nTask:\n{prompt}"

        messages = []
        if self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))
        messages.append(HumanMessage(content=prompt))

        # Retry logic
        last_error: str | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.llm.invoke(messages)
                latency_ms = (time.perf_counter() - start_time) * 1000

                usage = response.usage_metadata or {}
                print(f"LangChain: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out - {latency_ms:.0f}ms")
                return BaselineResult(
                    task_id=task_input.task_id,
                    output=response.content,
                    success=True,
                    latency_ms=latency_ms,
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    llm_calls=attempt + 1,
                )
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2**attempt))

        latency_ms = (time.perf_counter() - start_time) * 1000
        return BaselineResult(
            task_id=task_input.task_id,
            output="",
            success=False,
            error=last_error,
            latency_ms=latency_ms,
            llm_calls=self.max_retries,
        )
