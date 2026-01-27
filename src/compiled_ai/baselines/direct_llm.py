"""Direct LLM Baseline: Per-transaction prompting with no compilation."""

import time
from pathlib import Path
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
        log_dir: str | None = "logs",
    ) -> None:
        """Initialize the Direct LLM baseline.

        Args:
            provider: LLM provider ("anthropic", "openai", or "gemini")
            model: Model name. Defaults to provider's default model.
            system_prompt: Optional system prompt to use
            max_retries: Maximum retry attempts on failure
            retry_delay: Base delay between retries (exponential backoff)
            enable_cache: Whether to cache LLM responses
            verbose: Enable verbose logging
            log_dir: Directory for execution logs (None to disable file logging)
        """
        self.provider = provider
        self.verbose = verbose
        self.log_dir = Path(log_dir) if log_dir else None
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

        # Current log file for this execution
        self._current_log_file: Path | None = None

    def _default_model(self, provider: str) -> str:
        """Get default model for provider.

        Args:
            provider: LLM provider name

        Returns:
            Default model name for the provider
        """
        defaults = {
            "anthropic": "claude-opus-4-5-20251101",
            "openai": "gpt-4o",
            "gemini": "gemini-2.0-flash",
        }
        return defaults.get(provider, "claude-opus-4-5-20251101")

    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled and write to log file."""
        if self.verbose:
            print(f"[DirectLLM] {message}")
        self._log_to_file(message)

    def _log_to_file(self, message: str, section: str | None = None) -> None:
        """Write message to current log file.

        Args:
            message: Message to log
            section: Optional section header
        """
        if not self._current_log_file:
            return

        with open(self._current_log_file, "a", encoding="utf-8") as f:
            if section:
                f.write(f"\n{'='*80}\n")
                f.write(f"{section}\n")
                f.write(f"{'='*80}\n")
            f.write(f"{message}\n")

    def _setup_log_file(self, task_id: str) -> None:
        """Set up a new log file for this execution.

        Args:
            task_id: Task identifier for naming the log file
        """
        if not self.log_dir:
            self._current_log_file = None
            return

        # Create logs directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create log file (no timestamp needed, each run has its own directory)
        log_filename = f"{task_id}.log"
        self._current_log_file = self.log_dir / log_filename

        # Write header
        from datetime import datetime
        self._log_to_file(f"Direct LLM Execution Log", section="HEADER")
        self._log_to_file(f"Task ID: {task_id}")
        self._log_to_file(f"Timestamp: {datetime.now().isoformat()}")
        self._log_to_file(f"Provider: {self.provider}")
        self._log_to_file(f"Model: {self.config.model}")
        self._log_to_file(f"Max Retries: {self.max_retries}")
        if self.config.system_prompt:
            self._log_to_file(f"System Prompt: {self.config.system_prompt}")

    def run(self, task_input: TaskInput) -> BaselineResult:
        """Execute LLM inference for a single task.

        Args:
            task_input: Task input with prompt and context

        Returns:
            BaselineResult with output and metrics
        """
        # Set up log file for this task
        self._setup_log_file(task_input.task_id)

        start_time = time.perf_counter()

        # Log task input
        self._log_to_file(
            f"Original Prompt: {task_input.prompt}\n"
            f"Context: {task_input.context}",
            section="TASK INPUT"
        )

        # Build prompt with context
        # For DocILE and similar tasks, the prompt already includes all necessary data
        # Only add context for tasks that need it (e.g., BFCL with user_query/functions)
        prompt = task_input.prompt
        if task_input.context:
            # Only add context fields that aren't already in the prompt
            # For DocILE: document_text is already in prompt, so skip it
            # For BFCL: user_query and functions need to be added
            context_items = []
            for k, v in task_input.context.items():
                # Skip fields that are likely already in the formatted prompt
                # (document_text, document_path, task_type for DocILE)
                if k not in ("document_text", "document_path", "task_type"):
                    context_items.append(f"{k}: {v}")
            
            if context_items:
                context_str = "\n".join(context_items)
                prompt = f"Context:\n{context_str}\n\nTask:\n{prompt}"

        # Log full prompt sent to LLM
        self._log_to_file(prompt, section="LLM PROMPT")
        self._log(f"Executing task {task_input.task_id}")

        # Retry logic with exponential backoff
        last_error: str | None = None
        responses = []

        for attempt in range(self.max_retries):
            try:
                self._log(f"Attempt {attempt + 1}/{self.max_retries}")
                response = self.client.generate(prompt)
                responses.append(response)
                self.token_tracker.record(response)

                latency_ms = (time.perf_counter() - start_time) * 1000

                # Log successful response
                self._log_to_file(
                    f"Content: {response.content}\n"
                    f"Input Tokens: {response.input_tokens}\n"
                    f"Output Tokens: {response.output_tokens}\n"
                    f"Latency: {latency_ms:.2f}ms",
                    section=f"LLM RESPONSE (Attempt {attempt + 1})"
                )

                # Log final result
                self._log_to_file(
                    f"SUCCESS!\n"
                    f"Output: {response.content}\n"
                    f"Total Attempts: {attempt + 1}\n"
                    f"Total Latency: {latency_ms:.2f}ms\n"
                    f"Input Tokens: {response.input_tokens}\n"
                    f"Output Tokens: {response.output_tokens}",
                    section="FINAL RESULT"
                )

                self._log(f"Success on attempt {attempt + 1}")

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
                self._log_to_file(
                    f"Error: {last_error}",
                    section=f"ERROR (Attempt {attempt + 1})"
                )
                self._log(f"Error on attempt {attempt + 1}: {last_error}")

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    self._log(f"Retrying in {delay}s...")
                    time.sleep(delay)  # Exponential backoff

        # All retries failed
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Log final failure
        self._log_to_file(
            f"FAILED!\n"
            f"Error: {last_error}\n"
            f"Total Attempts: {self.max_retries}\n"
            f"Total Latency: {latency_ms:.2f}ms",
            section="FINAL RESULT"
        )

        self._log(f"Failed after {self.max_retries} attempts")

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
