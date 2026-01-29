"""LangChain Baseline: LangChain with native tool calling for comparison."""

import json
import os
import time
from typing import Any

from dotenv import load_dotenv

from .base import BaseBaseline, BaselineResult, TaskInput, register_baseline

load_dotenv()


@register_baseline("langchain")
class LangChainBaseline(BaseBaseline):
    """LangChain baseline with native tool calling.

    Uses LangChain's bind_tools() for proper function calling comparison.
    This represents realistic LangChain usage for function calling tasks.
    """

    description = "LangChain with native tool calling"

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
            "anthropic": "claude-opus-4-5-20251101",
            "openai": "gpt-4o",
        }
        return defaults.get(provider, "claude-opus-4-5-20251101")

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

        # Generic: look for tools/context provided by dataset converters/adapters
        tools = task_input.context.get("tools") or []
        tool_name_mapping: dict[str, str] = task_input.context.get(
            "tool_name_mapping", {}
        )

        # Build the user message (fallback to prompt if no explicit user_query)
        user_query = task_input.context.get("user_query", task_input.prompt)
        
        messages = []
        if self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))
        messages.append(HumanMessage(content=user_query))

        # Retry logic
        last_error: str | None = None
        for attempt in range(self.max_retries):
            try:
                # If we have tools, use tool calling
                if tools:
                    llm_with_tools = self.llm.bind_tools(tools)
                    response = llm_with_tools.invoke(messages)
                    
                    # Extract tool calls from response
                    if response.tool_calls:
                        # Format as generic function call output
                        tool_call = response.tool_calls[0]
                        # Map sanitized name back to original
                        original_name = tool_name_mapping.get(
                            tool_call["name"], tool_call["name"]
                        )
                        output = json.dumps({
                            "name": original_name,
                            "arguments": tool_call["args"]
                        })
                    else:
                        # Model didn't make a tool call, use content
                        output = response.content
                else:
                    # No functions - standard invoke
                    response = self.llm.invoke(messages)
                    output = response.content

                latency_ms = (time.perf_counter() - start_time) * 1000
                usage = response.usage_metadata or {}
                
                print(f"LangChain: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out - {latency_ms:.0f}ms", flush=True)
                
                return BaselineResult(
                    task_id=task_input.task_id,
                    output=output,
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
