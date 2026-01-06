"""Unified LLM client abstraction for Claude and OpenAI APIs."""

import hashlib
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
import openai
from dotenv import load_dotenv

from .logging import get_logger, log_latency, log_tokens

load_dotenv()
logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Response from an LLM API call."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: float
    cached: bool = False

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.input_tokens + self.output_tokens


@dataclass
class LLMConfig:
    """Configuration for LLM API calls."""

    model: str
    temperature: float = 0.0
    max_tokens: int = 4096
    system_prompt: str | None = None


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(
        self,
        config: LLMConfig,
        enable_cache: bool = False,
        cache_dir: str | None = None,
    ) -> None:
        """Initialize the LLM client.

        Args:
            config: LLM configuration
            enable_cache: Whether to cache responses
            cache_dir: Directory for cache files
        """
        self.config = config
        self.enable_cache = enable_cache or os.getenv("ENABLE_RESPONSE_CACHE", "").lower() == "true"
        self.cache_dir = Path(cache_dir or os.getenv("CACHE_DIR", ".cache/llm_responses"))

        if self.enable_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: The user prompt
            **kwargs: Additional arguments for the API call

        Returns:
            LLMResponse with content and metadata
        """
        ...

    def _get_cache_key(self, prompt: str, **kwargs: Any) -> str:
        """Generate a cache key for a request."""
        cache_data = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "system_prompt": self.config.system_prompt,
            "prompt": prompt,
            **kwargs,
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> LLMResponse | None:
        """Retrieve a cached response if available."""
        if not self.enable_cache:
            return None

        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                return LLMResponse(
                    content=data["content"],
                    input_tokens=data["input_tokens"],
                    output_tokens=data["output_tokens"],
                    model=data["model"],
                    latency_ms=0.0,
                    cached=True,
                )
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def _cache_response(self, cache_key: str, response: LLMResponse) -> None:
        """Cache a response."""
        if not self.enable_cache:
            return

        cache_file = self.cache_dir / f"{cache_key}.json"
        cache_data = {
            "content": response.content,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "model": response.model,
        }
        cache_file.write_text(json.dumps(cache_data, indent=2))


class AnthropicClient(LLMClient):
    """Claude API client."""

    def __init__(
        self,
        config: LLMConfig | None = None,
        api_key: str | None = None,
        enable_cache: bool = False,
        cache_dir: str | None = None,
    ) -> None:
        """Initialize the Anthropic client.

        Args:
            config: LLM configuration. Defaults to Claude Sonnet.
            api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
            enable_cache: Whether to cache responses
            cache_dir: Directory for cache files
        """
        config = config or LLMConfig(
            model=os.getenv("DEFAULT_MODEL", "claude-sonnet-4-20250514")
        )
        super().__init__(config, enable_cache, cache_dir)

        self.client = anthropic.Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        )

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate a response using Claude.

        Args:
            prompt: The user prompt
            **kwargs: Additional arguments for the API call

        Returns:
            LLMResponse with content and metadata
        """
        cache_key = self._get_cache_key(prompt, **kwargs)
        cached = self._get_cached_response(cache_key)
        if cached:
            log_tokens(cached.input_tokens, cached.output_tokens, cached=True)
            return cached

        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

        start_time = time.perf_counter()
        response = self.client.messages.create(
            model=kwargs.get("model", self.config.model),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            system=kwargs.get("system_prompt", self.config.system_prompt) or "",
            messages=messages,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000

        content = response.content[0].text if response.content else ""

        result = LLMResponse(
            content=content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
            latency_ms=latency_ms,
            cached=False,
        )

        log_tokens(result.input_tokens, result.output_tokens)
        log_latency(latency_ms, "Claude API")

        self._cache_response(cache_key, result)
        return result


class OpenAIClient(LLMClient):
    """OpenAI API client."""

    def __init__(
        self,
        config: LLMConfig | None = None,
        api_key: str | None = None,
        enable_cache: bool = False,
        cache_dir: str | None = None,
    ) -> None:
        """Initialize the OpenAI client.

        Args:
            config: LLM configuration. Defaults to GPT-4o.
            api_key: OpenAI API key. Defaults to OPENAI_API_KEY env var.
            enable_cache: Whether to cache responses
            cache_dir: Directory for cache files
        """
        config = config or LLMConfig(model="gpt-4o")
        super().__init__(config, enable_cache, cache_dir)

        self.client = openai.OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY")
        )

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate a response using OpenAI.

        Args:
            prompt: The user prompt
            **kwargs: Additional arguments for the API call

        Returns:
            LLMResponse with content and metadata
        """
        cache_key = self._get_cache_key(prompt, **kwargs)
        cached = self._get_cached_response(cache_key)
        if cached:
            log_tokens(cached.input_tokens, cached.output_tokens, cached=True)
            return cached

        messages: list[dict[str, str]] = []

        system_prompt = kwargs.get("system_prompt", self.config.system_prompt)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        start_time = time.perf_counter()
        response = self.client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            messages=messages,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000

        content = response.choices[0].message.content or ""
        usage = response.usage

        result = LLMResponse(
            content=content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=response.model,
            latency_ms=latency_ms,
            cached=False,
        )

        log_tokens(result.input_tokens, result.output_tokens)
        log_latency(latency_ms, "OpenAI API")

        self._cache_response(cache_key, result)
        return result


@dataclass
class TokenTracker:
    """Tracks cumulative token usage across multiple LLM calls."""

    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    cached_calls: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    def record(self, response: LLMResponse) -> None:
        """Record token usage from a response."""
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.calls += 1
        if response.cached:
            self.cached_calls += 1
        else:
            self.latencies_ms.append(response.latency_ms)

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def avg_latency_ms(self) -> float:
        """Average latency for non-cached calls."""
        if not self.latencies_ms:
            return 0.0
        return sum(self.latencies_ms) / len(self.latencies_ms)


def create_client(
    provider: str = "anthropic",
    config: LLMConfig | None = None,
    enable_cache: bool = False,
) -> LLMClient:
    """Factory function to create an LLM client.

    Args:
        provider: "anthropic" or "openai"
        config: LLM configuration
        enable_cache: Whether to cache responses

    Returns:
        Configured LLM client
    """
    if provider == "anthropic":
        return AnthropicClient(config=config, enable_cache=enable_cache)
    elif provider == "openai":
        return OpenAIClient(config=config, enable_cache=enable_cache)
    else:
        raise ValueError(f"Unknown provider: {provider}")
