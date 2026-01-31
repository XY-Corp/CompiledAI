"""Crush-based workflow generator for CompiledAI.

Uses Crush (OpenCode) with Claude Opus to generate workflows and activities
from natural language descriptions.
"""

from .generator import CrushGenerator, GenerationResult
from .runner import CrushRunner

__all__ = [
    "CrushGenerator",
    "GenerationResult",
    "CrushRunner",
]
