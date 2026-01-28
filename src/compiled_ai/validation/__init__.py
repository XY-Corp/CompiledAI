"""Validation Pipeline: 4-stage code validation (Security, Syntax, Execution, Accuracy).

This module provides security validators for the CompiledAI code generation pipeline:

- **SASTValidator**: Static Application Security Testing (Bandit, detect-secrets, Semgrep)

Example:
    from compiled_ai.validation import SASTValidator

    validator = SASTValidator(severity_threshold="high")
    result = validator.validate(generated_code)
    if result.is_threat:
        print(f"Security issues: {result.details['issues']}")
"""

from .sast import SASTValidator, SASTResult, SASTIssue, scan_directory

__all__ = [
    "SASTValidator",
    "SASTResult",
    "SASTIssue",
    "scan_directory",
]
