"""Baseline Implementations: Direct LLM, Code Factory, LangChain, Multi-agent comparisons."""

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
from .code_factory import CodeFactoryBaseline
from .langchain_baseline import LangChainBaseline
from .autogen_baseline import AutoGenBaseline

__all__ = [
    "BaseBaseline",
    "BaselineResult",
    "TaskInput",
    "TaskOutput",
    "DirectLLMBaseline",
    "CodeFactoryBaseline",
    "LangChainBaseline",
    "AutoGenBaseline",
    "get_baseline",
    "list_baselines",
    "register_baseline",
]
