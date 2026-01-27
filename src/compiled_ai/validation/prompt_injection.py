"""Prompt injection detection using ProtectAI's DeBERTa model.

This module provides protection against prompt injection attacks using
ProtectAI's deberta-v3-base-prompt-injection-v2 model via transformers.

The model is 184M parameters and runs on CPU (~100ms inference).
No HuggingFace login required.

References:
- ProtectAI Model: https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2
- OWASP LLM01:2025 Prompt Injection
"""

from __future__ import annotations

import logging
from typing import Any

from .base import ValidationResult, Validator, register_validator

logger = logging.getLogger(__name__)


@register_validator("prompt_injection")
class PromptInjectionValidator(Validator):
    """Validates input for prompt injection attacks using ProtectAI's DeBERTa model.

    Uses ProtectAI's deberta-v3-base-prompt-injection-v2 model which is fine-tuned to detect:
    - Prompt injection attempts
    - Jailbreak attempts

    The model runs on CPU by default (~100ms per inference).
    No HuggingFace login required.

    Attributes:
        threshold: Probability threshold for injection classification (default 0.5)
        device: Device to run on ("cpu", "cuda", or "mps", default "cpu")

    Example:
        validator = PromptInjectionValidator()
        result = validator.validate("Ignore all previous instructions")
        if result.is_threat:
            print(f"Injection detected! Score: {result.details['injection_score']}")
    """

    # Class-level model cache to avoid reloading
    _classifier = None
    _model_name = "protectai/deberta-v3-base-prompt-injection-v2"

    def __init__(
        self,
        threshold: float = 0.5,
        device: str = "cpu",
    ):
        """Initialize the prompt injection validator.

        Args:
            threshold: Minimum probability to classify as injection (0.0-1.0)
            device: Device to run model on ("cpu", "cuda", or "mps")
        """
        self.threshold = threshold
        self.device = device

    def _get_classifier(self) -> Any:
        """Lazy-load the ProtectAI classifier."""
        if PromptInjectionValidator._classifier is None:
            try:
                from transformers import pipeline

                logger.info(f"Loading ProtectAI model: {self._model_name}")
                PromptInjectionValidator._classifier = pipeline(
                    "text-classification",
                    model=self._model_name,
                    device=self.device if self.device == "cpu" else 0,
                )
                logger.info("ProtectAI model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load ProtectAI model: {e}")
                raise

        return PromptInjectionValidator._classifier

    def validate(self, content: str, **kwargs: Any) -> ValidationResult:
        """Validate content for prompt injection attempts.

        Args:
            content: The text to validate (user input, prompt, etc.)
            **kwargs: Additional parameters (unused)

        Returns:
            ValidationResult with:
                - success: True if no injection detected (SAFE)
                - score: Safety score (1.0 = safe, 0.0 = injection)
                - details: label, injection_score, safe_score
        """
        if not content or not content.strip():
            return ValidationResult(
                success=True,
                score=1.0,
                details={"reason": "empty_content"},
            )

        try:
            classifier = self._get_classifier()

            # Run classification
            result = classifier(content)

            # Parse result - model returns list with single dict
            if isinstance(result, list) and len(result) > 0:
                prediction = result[0]
            else:
                prediction = result

            label = prediction.get("label", "").upper()
            score = prediction.get("score", 0.0)

            # ProtectAI model labels: "SAFE" or "INJECTION"
            is_safe_label = label == "SAFE"

            # Calculate scores
            if is_safe_label:
                safe_score = score
                injection_score = 1.0 - score
            else:
                injection_score = score
                safe_score = 1.0 - score

            # Check against threshold
            is_safe = injection_score < self.threshold

            return ValidationResult(
                success=is_safe,
                score=safe_score,
                details={
                    "label": label,
                    "raw_label": prediction.get("label"),
                    "raw_score": score,
                    "injection_score": injection_score,
                    "safe_score": safe_score,
                    "threshold": self.threshold,
                    "model": self._model_name,
                },
            )

        except Exception as e:
            logger.error(f"Prompt injection validation failed: {e}")
            return ValidationResult(
                success=False,
                score=0.0,
                details={"error": str(e)},
                error=str(e),
            )
