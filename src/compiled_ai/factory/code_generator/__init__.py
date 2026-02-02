"""OpenCode-based workflow generator for CompiledAI.

This module provides AI-powered workflow generation using OpenCode CLI
with Claude or other language models. It generates complete, validated
CompiledAI workflows from natural language descriptions.

Features:
- Natural language to workflow conversion
- Per-activity code generation with precise specs
- Automatic validation against specs
- Iterative refinement with error correction
- Security validation integration
- Metrics and logging

Quick Start:
    from compiled_ai.factory.code_generator import CodeGenerator

    generator = CodeGenerator()
    result = generator.generate(
        "Create a workflow that validates and processes email addresses"
    )

    if result.success:
        print(f"Workflow: {result.workflow_path}")
        print(f"Activities: {result.activities_path}")

CLI Usage:
    # Generate a workflow
    python -m compiled_ai.factory.code_generator "Your task description"

    # With options
    python -m compiled_ai.factory.code_generator \\
        -o ./output \\
        -m anthropic/claude-sonnet-4 \\
        --json \\
        "Build a data processing pipeline"

See Also:
    - CodeGenerator: Main generator class
    - GenerationResult: Generation result container
    - GenerationMetrics: Metrics tracking
    - ActivitySpec: Activity specification model
"""

from .generator import (
    CodeGenerator,
    GenerationMetrics,
    GenerationResult,
    GenerationStage,
    MetricEntry,
    ValidationIssue,
)
from .models import (
    ActivitySpec,
    GeneratedActivity,
    InputSpec,
    OutputSpec,
    WorkflowSpec,
)
from .runner import OpenCodeOutput, OpenCodeRunner
from .validator import ValidationResult, validate_activity, validate_syntax

__all__ = [
    # Core generator
    "CodeGenerator",
    "GenerationResult",
    # Runner
    "OpenCodeRunner",
    "OpenCodeOutput",
    # Models
    "ActivitySpec",
    "InputSpec",
    "OutputSpec",
    "WorkflowSpec",
    "GeneratedActivity",
    # Metrics
    "GenerationMetrics",
    "MetricEntry",
    "GenerationStage",
    # Validation
    "ValidationIssue",
    "ValidationResult",
    "validate_activity",
    "validate_syntax",
]

__version__ = "0.3.0"
