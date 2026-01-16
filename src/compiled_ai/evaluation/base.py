"""Base evaluator interface and registry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationResult:
    """Result of evaluating an output against expected."""

    success: bool
    score: float  # 0.0 to 1.0
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def passed(self) -> bool:
        """Alias for success."""
        return self.success


class Evaluator(ABC):
    """Base class for output evaluators."""

    name: str = "base"

    @abstractmethod
    def evaluate(self, output: str, expected: Any, **kwargs: Any) -> EvaluationResult:
        """Evaluate output against expected result.

        Args:
            output: The LLM output to evaluate
            expected: The expected result (format depends on evaluator)
            **kwargs: Additional evaluation parameters

        Returns:
            EvaluationResult with success, score, and details
        """
        ...


# Evaluator registry
_EVALUATOR_REGISTRY: dict[str, type[Evaluator]] = {}


def register_evaluator(name: str):
    """Decorator to register an evaluator.

    Args:
        name: Unique name for the evaluator

    Returns:
        Decorator that registers the evaluator class
    """

    def decorator(cls: type[Evaluator]) -> type[Evaluator]:
        _EVALUATOR_REGISTRY[name] = cls
        cls.name = name
        return cls

    return decorator


def get_evaluator(name: str, **kwargs: Any) -> Evaluator:
    """Get an evaluator by name.

    Args:
        name: Evaluator name (exact_match, fuzzy_match, json_match, ast_match, schema)
        **kwargs: Arguments to pass to the evaluator constructor

    Returns:
        Initialized evaluator instance

    Raises:
        ValueError: If evaluator name is not found
    """
    if name not in _EVALUATOR_REGISTRY:
        available = list(_EVALUATOR_REGISTRY.keys())
        raise ValueError(f"Unknown evaluator: {name}. Available: {available}")

    return _EVALUATOR_REGISTRY[name](**kwargs)


def list_evaluators() -> list[str]:
    """List available evaluator names.

    Returns:
        List of registered evaluator names
    """
    return list(_EVALUATOR_REGISTRY.keys())
