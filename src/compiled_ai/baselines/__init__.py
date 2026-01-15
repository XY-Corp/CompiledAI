"""Baseline Implementations: Direct LLM, LangChain, Multi-agent comparisons."""

from .base import (
    BaseBaseline,
    BaselineResult,
    TaskInput,
    TaskOutput,
    get_baseline,
    list_baselines,
    register_baseline,
)
from .direct_llm import DirectLLMBaseline

__all__ = [
    "BaseBaseline",
    "BaselineResult",
    "TaskInput",
    "TaskOutput",
    "DirectLLMBaseline",
    "get_baseline",
    "list_baselines",
    "register_baseline",
]
