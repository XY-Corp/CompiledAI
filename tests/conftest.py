"""Pytest fixtures for Compiled AI benchmark tests."""

import os
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from compiled_ai.metrics.base import BenchmarkMetadata, MetricsCollector
from compiled_ai.metrics.latency import LatencyMetrics
from compiled_ai.metrics.token_efficiency import TokenMetrics
from compiled_ai.utils.llm_client import LLMConfig, LLMResponse


# --- Mock LLM Client ---


@dataclass
class MockLLMResponse:
    """Mock LLM response for testing."""

    content: str = "def process(data): return data"
    input_tokens: int = 100
    output_tokens: int = 50
    model: str = "mock-model"
    latency_ms: float = 150.0
    cached: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class MockLLMClient:
    """Mock LLM client for testing without API calls."""

    def __init__(
        self,
        config: LLMConfig | None = None,
        responses: list[str] | None = None,
    ) -> None:
        self.config = config or LLMConfig(model="mock-model")
        self.responses = responses or ["def process(data): return data"]
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Return mock response."""
        self.calls.append({"prompt": prompt, **kwargs})
        response_content = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1

        return LLMResponse(
            content=response_content,
            input_tokens=len(prompt.split()) * 2,  # Rough estimate
            output_tokens=len(response_content.split()) * 2,
            model=self.config.model,
            latency_ms=50.0,
            cached=False,
        )


@pytest.fixture
def mock_llm_client() -> MockLLMClient:
    """Provide a mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def mock_llm_config() -> LLMConfig:
    """Provide a default LLM config."""
    return LLMConfig(
        model="claude-sonnet-4-20250514",
        temperature=0.0,
        max_tokens=4096,
    )


# --- Metrics Fixtures ---


@pytest.fixture
def sample_token_metrics() -> TokenMetrics:
    """Provide sample token metrics."""
    metrics = TokenMetrics()
    metrics.record_generation(input_tokens=500, output_tokens=200, loc=42)
    return metrics


@pytest.fixture
def sample_runtime_token_metrics() -> TokenMetrics:
    """Provide sample runtime token metrics (simulating per-tx LLM calls)."""
    metrics = TokenMetrics()
    # Simulate 10 transactions with ~200 tokens each
    for _ in range(10):
        metrics.record_runtime_tx(200)
    return metrics


@pytest.fixture
def sample_latency_metrics() -> LatencyMetrics:
    """Provide sample latency metrics."""
    metrics = LatencyMetrics()
    # Simulate 100 measurements with low variance (compiled-like)
    import random

    random.seed(42)
    for _ in range(100):
        metrics.record(50 + random.gauss(0, 5))  # ~50ms with low variance
    metrics.record_cold_start(2500.0)  # 2.5s cold start
    return metrics


@pytest.fixture
def sample_runtime_latency_metrics() -> LatencyMetrics:
    """Provide sample runtime latency metrics (high variance)."""
    metrics = LatencyMetrics()
    # Simulate 100 measurements with high variance (runtime-like)
    import random

    random.seed(42)
    for _ in range(100):
        metrics.record(500 + random.gauss(0, 200))  # ~500ms with high variance
    return metrics


@pytest.fixture
def metrics_collector() -> MetricsCollector:
    """Provide a metrics collector with metadata."""
    metadata = BenchmarkMetadata(
        benchmark_id="test_run_001",
        task_name="test_task",
        method="compiled",
        model="claude-sonnet-4-20250514",
    )
    return MetricsCollector(metadata)


# --- Environment Fixtures ---


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up mock environment variables."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENABLE_RESPONSE_CACHE", "false")


@pytest.fixture
def temp_cache_dir(tmp_path: Any) -> str:
    """Provide a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return str(cache_dir)


# --- Sample Data Fixtures ---


@pytest.fixture
def sample_yaml_spec() -> dict[str, Any]:
    """Provide a sample workflow specification."""
    return {
        "name": "test_workflow",
        "version": "1.0",
        "category": "document_processing",
        "description": "Test workflow for unit tests",
        "template": "SimpleAgent",
        "modules": ["database", "http"],
        "compliance": ["hipaa"],
        "input_schema": {
            "type": "object",
            "properties": {
                "document": {"type": "string"},
                "patient_id": {"type": "string"},
            },
            "required": ["document", "patient_id"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string"},
                "amount": {"type": "number"},
            },
        },
        "business_logic": "Extract claim ID and amount from document.",
        "accuracy_threshold": 0.95,
    }


@pytest.fixture
def sample_generated_code() -> str:
    """Provide sample generated code."""
    return '''
def process_business_logic(document: str, patient_id: str) -> dict:
    """Extract claim information from document.

    Args:
        document: Raw document text
        patient_id: Patient identifier

    Returns:
        Dictionary with claim_id and amount
    """
    # Extract claim ID (simplified for testing)
    claim_id = None
    for line in document.split("\\n"):
        if "claim" in line.lower():
            parts = line.split(":")
            if len(parts) > 1:
                claim_id = parts[1].strip()
                break

    # Extract amount (simplified)
    amount = 0.0
    for line in document.split("\\n"):
        if "$" in line:
            try:
                amount = float(line.split("$")[1].split()[0].replace(",", ""))
            except (IndexError, ValueError):
                pass

    return {
        "claim_id": claim_id or "UNKNOWN",
        "amount": amount,
    }
'''
