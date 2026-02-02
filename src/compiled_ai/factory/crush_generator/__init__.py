"""Crush-based workflow generator for CompiledAI.

This module provides AI-powered workflow generation using Crush (OpenCode CLI)
with Claude or other language models. It generates complete, validated
CompiledAI workflows from natural language descriptions.

Features:
- Natural language to workflow conversion
- Automatic activity code generation
- Iterative refinement with error correction
- Security validation integration
- Metrics and logging

Quick Start:
    from compiled_ai.factory.crush_generator import CrushGenerator
    
    generator = CrushGenerator()
    result = generator.generate(
        "Create a workflow that validates and processes email addresses"
    )
    
    if result.success:
        print(f"Workflow: {result.workflow_path}")
        print(f"Activities: {result.activities_path}")

CLI Usage:
    # Generate a workflow
    python -m compiled_ai.factory.crush_generator "Your task description"
    
    # With options
    python -m compiled_ai.factory.crush_generator \\
        -o ./output \\
        -m anthropic/claude-sonnet-4 \\
        --json \\
        "Build a data processing pipeline"

See Also:
    - CrushGenerator: Main generator class
    - GenerationResult: Generation result container
    - GenerationMetrics: Metrics tracking
"""

from .generator import (
    CrushGenerator,
    GenerationResult,
    GenerationMetrics,
    GenerationStage,
    MetricEntry,
    ValidationIssue,
)
from .runner import CrushRunner, CrushOutput

__all__ = [
    # Core classes
    "CrushGenerator",
    "GenerationResult",
    "CrushRunner",
    "CrushOutput",
    # Metrics
    "GenerationMetrics",
    "MetricEntry",
    "GenerationStage",
    # Validation
    "ValidationIssue",
]

__version__ = "0.2.0"
