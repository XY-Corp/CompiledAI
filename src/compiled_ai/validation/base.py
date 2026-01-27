"""Base validator interface and registry for security validation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Result of validating content for security threats.

    Attributes:
        success: True if content passed validation (no threats detected)
        score: Confidence score from 0.0 (definite threat) to 1.0 (safe)
        details: Additional information about the validation
        error: Error message if validation failed unexpectedly
    """

    success: bool
    score: float  # 0.0 to 1.0 (1.0 = safe, 0.0 = definite threat)
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def passed(self) -> bool:
        """Alias for success."""
        return self.success

    @property
    def is_threat(self) -> bool:
        """True if a security threat was detected."""
        return not self.success


class Validator(ABC):
    """Base class for security validators.

    Validators check content for security threats such as prompt injection,
    jailbreak attempts, or unsafe code patterns.
    """

    name: str = "base"

    @abstractmethod
    def validate(self, content: str, **kwargs: Any) -> ValidationResult:
        """Validate content for security threats.

        Args:
            content: The content to validate (prompt, code, etc.)
            **kwargs: Additional validation parameters

        Returns:
            ValidationResult with success, score, and details
        """
        ...


# Validator registry
_VALIDATOR_REGISTRY: dict[str, type[Validator]] = {}


def register_validator(name: str) -> Callable[[type[Validator]], type[Validator]]:
    """Decorator to register a validator.

    Args:
        name: Unique name for the validator

    Returns:
        Decorator that registers the validator class

    Example:
        @register_validator("prompt_injection")
        class PromptInjectionValidator(Validator):
            ...
    """

    def decorator(cls: type[Validator]) -> type[Validator]:
        _VALIDATOR_REGISTRY[name] = cls
        cls.name = name
        return cls

    return decorator


def get_validator(name: str, **kwargs: Any) -> Validator:
    """Get a validator by name.

    Args:
        name: Validator name (e.g., "prompt_injection", "canary")
        **kwargs: Arguments to pass to the validator constructor

    Returns:
        Initialized validator instance

    Raises:
        ValueError: If validator name is not found
    """
    if name not in _VALIDATOR_REGISTRY:
        available = list(_VALIDATOR_REGISTRY.keys())
        raise ValueError(f"Unknown validator: {name}. Available: {available}")

    return _VALIDATOR_REGISTRY[name](**kwargs)


def list_validators() -> list[str]:
    """List available validator names.

    Returns:
        List of registered validator names
    """
    return list(_VALIDATOR_REGISTRY.keys())
