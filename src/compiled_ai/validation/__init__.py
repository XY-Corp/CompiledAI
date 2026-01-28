"""Validation Pipeline: 4-stage code validation (Security, Syntax, Execution, Accuracy).

This module provides security validators for the CompiledAI code generation pipeline:

- **PromptInjectionValidator**: Detects prompt injection attacks using Prompt Guard
- **CanaryManager**: Detects system prompt leakage via canary tokens
- **CodeShieldValidator**: Validates generated code for security vulnerabilities
- **PIIScanner**: Detects and optionally redacts PII for GDPR/SOC2 compliance

Example:
    from compiled_ai.validation import (
        PromptInjectionValidator,
        CanaryManager,
        CodeShieldValidator,
        PIIScanner,
    )

    # Input validation
    injection_validator = PromptInjectionValidator()
    result = injection_validator.validate(user_input)
    if result.is_threat:
        raise SecurityError("Prompt injection detected")

    # Canary token for leakage detection
    canary_manager = CanaryManager()
    prompt = canary_manager.inject_into_prompt(system_prompt, session_id)
    # ... after LLM response ...
    if canary_manager.check_leakage(response, session_id).leaked:
        raise SecurityError("System prompt leaked")

    # Output code validation
    code_validator = CodeShieldValidator()
    result = code_validator.validate(generated_code)
    if result.is_threat:
        raise SecurityError(f"Unsafe code: {result.details['issues']}")

    # PII scanning
    pii_scanner = PIIScanner(redact=True)
    result = pii_scanner.validate(user_data)
    sanitized_text = result.details.get("redacted_text")
"""

from .base import (
    ValidationResult,
    Validator,
    get_validator,
    list_validators,
    register_validator,
)
from .canary import (
    CanaryManager,
    CanaryToken,
    LeakageResult,
    get_canary_manager,
)
from .code_shield import CodeShieldValidator
from .pii_scanner import PIIScanner
from .prompt_injection import PromptInjectionValidator

__all__ = [
    # Base
    "Validator",
    "ValidationResult",
    "register_validator",
    "get_validator",
    "list_validators",
    # Prompt Injection
    "PromptInjectionValidator",
    # Canary Tokens
    "CanaryManager",
    "CanaryToken",
    "LeakageResult",
    "get_canary_manager",
    # Code Shield
    "CodeShieldValidator",
    # PII Scanner
    "PIIScanner",
]
