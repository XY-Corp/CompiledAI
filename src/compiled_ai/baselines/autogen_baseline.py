"""AutoGen Baseline: Multi-agent coordination for comparison."""

import asyncio
import os
import time
from typing import Any

from dotenv import load_dotenv

from .base import BaseBaseline, BaselineResult, TaskInput, register_baseline

load_dotenv()


@register_baseline("autogen")
class AutoGenBaseline(BaseBaseline):
    """AutoGen multi-agent baseline.

    Demonstrates multi-agent coordination overhead:
    - Multiple LLM calls per task (agent-to-agent)
    - Coordination/orchestration cost
    - Shows O(k*n) token consumption vs O(n) for direct
    """

    description = "AutoGen multi-agent coordination"

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
        self.enable_cache = enable_cache
        self._client = None
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_calls = 0

    def _default_model(self, provider: str) -> str:
        defaults = {
            "anthropic": "claude-opus-4-5-20251101",
            "openai": "gpt-4o",
        }
        return defaults.get(provider, "claude-opus-4-5-20251101")

    def _get_model_client(self) -> Any:
        """Get the appropriate AutoGen model client."""
        if self._client is not None:
            return self._client

        if self.provider == "anthropic":
            from autogen_ext.models.anthropic import AnthropicChatCompletionClient

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            self._client = AnthropicChatCompletionClient(model=self.model, api_key=api_key)
        elif self.provider == "openai":
            from autogen_ext.models.openai import OpenAIChatCompletionClient

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            self._client = OpenAIChatCompletionClient(model=self.model, api_key=api_key)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        return self._client

    async def _run_multi_agent(self, task_input: TaskInput) -> tuple[str, int, int, int]:
        """Run a multi-agent workflow for the task.

        Uses two agents:
        1. Planner: Analyzes the task and creates a plan
        2. Executor: Executes the plan and produces output

        Returns: (output, input_tokens, output_tokens, llm_calls)
        """
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.conditions import TextMentionTermination
        from autogen_agentchat.teams import RoundRobinGroupChat

        model_client = self._get_model_client()

        # Build the task prompt
        prompt = task_input.prompt
        if task_input.context:
            context_str = "\n".join(f"{k}: {v}" for k, v in task_input.context.items())
            prompt = f"Context:\n{context_str}\n\nTask:\n{prompt}"

        # Create two agents for multi-agent coordination
        planner = AssistantAgent(
            name="Planner",
            model_client=model_client,
            system_message=(
                "You are a planning agent. Analyze the task and create a brief plan. "
                "Keep your response concise. After planning, say HANDOFF to pass to executor."
            ),
        )

        executor = AssistantAgent(
            name="Executor",
            model_client=model_client,
            system_message=(
                "You are an execution agent. Given a plan, produce the final output. "
                "Output ONLY the required result (JSON, text, etc). "
                "When done, say TERMINATE."
            ),
        )

        # Termination condition
        termination = TextMentionTermination("TERMINATE")

        # Create team with round-robin chat
        team = RoundRobinGroupChat(
            participants=[planner, executor],
            termination_condition=termination,
            max_turns=4,  # Limit turns to control costs
        )

        # Run the team
        result = await team.run(task=prompt)

        # Extract output from the Executor's last message
        output = ""
        if result.messages:
            for msg in reversed(result.messages):
                # Only get messages from Executor agent (not Planner, not user)
                source = getattr(msg, "source", None)
                if source == "Executor":
                    content = msg.content if hasattr(msg, "content") else str(msg)
                    # Strip TERMINATE marker if present
                    if content:
                        output = content.replace("TERMINATE", "").strip()
                        break
            # Fallback to last assistant message if no Executor message
            if not output:
                for msg in reversed(result.messages):
                    content = msg.content if hasattr(msg, "content") else str(msg)
                    if content and "TERMINATE" not in content and "HANDOFF" not in content:
                        output = content
                        break

        # Count LLM calls (each message from an agent = 1 LLM call)
        llm_calls = sum(1 for msg in result.messages if hasattr(msg, "source") and msg.source in ["Planner", "Executor"])

        # Token tracking - AutoGen doesn't expose this directly
        # Estimate tokens from message content (~4 chars per token)
        input_tokens = 0
        output_tokens = 0
        
        for msg in result.messages:
            content = msg.content if hasattr(msg, "content") else str(msg)
            if not content:
                continue
            # Rough estimate: ~4 characters per token
            estimated_tokens = len(content) // 4
            
            source = getattr(msg, "source", None)
            if source in ["Planner", "Executor"]:
                # Agent output = output tokens
                output_tokens += estimated_tokens
            else:
                # User/system message = input tokens
                input_tokens += estimated_tokens
        
        # Add system prompt tokens to input (rough estimate for each agent)
        input_tokens += 100 * llm_calls  # ~100 tokens per system prompt

        return output, input_tokens, output_tokens, llm_calls

    def run(self, task_input: TaskInput) -> BaselineResult:
        """Execute AutoGen multi-agent workflow for a single task."""
        start_time = time.perf_counter()

        last_error: str | None = None

        for attempt in range(self.max_retries):
            try:
                # Run async workflow
                output, input_tokens, output_tokens, llm_calls = asyncio.run(
                    self._run_multi_agent(task_input)
                )

                latency_ms = (time.perf_counter() - start_time) * 1000

                self._total_input_tokens += input_tokens
                self._total_output_tokens += output_tokens
                self._total_calls += llm_calls

                print(f"AutoGen: ~{input_tokens} in / ~{output_tokens} out ({llm_calls} calls) - {latency_ms:.0f}ms")
                return BaselineResult(
                    task_id=task_input.task_id,
                    output=output,
                    success=True,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    llm_calls=llm_calls,
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

    def get_token_summary(self) -> dict[str, Any]:
        """Get cumulative token usage summary."""
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_tokens": self._total_input_tokens + self._total_output_tokens,
            "total_calls": self._total_calls,
            "cached_calls": 0,
            "avg_latency_ms": 0,
        }
