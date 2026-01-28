"""Prompt injection detection using ProtectAI's DeBERTa model.

This module provides protection against prompt injection attacks using
ProtectAI's deberta-v3-base-prompt-injection-v2 model via transformers.

The model is 184M parameters and runs on CPU (~100ms inference).
No HuggingFace login required.

Features:
- Detects prompt injection and jailbreak attempts
- Decodes obfuscated payloads (base64, hex, URL encoding, unicode escapes)

References:
- ProtectAI Model: https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2
- OWASP LLM01:2025 Prompt Injection
"""

from __future__ import annotations

import base64
import logging
import re
import urllib.parse
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

    # Encoding detection patterns
    # Base64: at least 20 chars of valid base64, optional padding
    BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
    # Hex: at least 20 hex chars (10 bytes), optional 0x prefix
    HEX_PATTERN = re.compile(r"(?:0x)?[0-9a-fA-F]{20,}")
    # Unicode escapes: at least 4 consecutive \uXXXX patterns
    UNICODE_ESCAPE_PATTERN = re.compile(r"(?:\\u[0-9a-fA-F]{4}){4,}")

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

    def _decode_content(self, content: str) -> list[str]:
        """Decode potentially encoded content and return all variants to check.

        Detects and decodes:
        - Base64 encoded strings
        - URL encoded strings
        - Hex encoded strings
        - Unicode escape sequences

        Args:
            content: The original content to analyze

        Returns:
            List of decoded variants (always includes original)
        """
        variants = [content]

        # 1. Base64 detection and decoding
        for match in self.BASE64_PATTERN.finditer(content):
            try:
                decoded = base64.b64decode(match.group()).decode("utf-8", errors="ignore")
                # Only add if it looks like text (has letters) and is long enough
                if decoded and len(decoded) > 10 and any(c.isalpha() for c in decoded):
                    variants.append(decoded)
                    logger.debug(f"Decoded base64: {decoded[:50]}...")
            except Exception:
                pass

        # 2. URL decoding
        try:
            url_decoded = urllib.parse.unquote(content)
            if url_decoded != content:
                variants.append(url_decoded)
                logger.debug(f"URL decoded: {url_decoded[:50]}...")
        except Exception:
            pass

        # 3. Hex decoding
        for match in self.HEX_PATTERN.finditer(content):
            try:
                hex_str = match.group().replace("0x", "").replace("0X", "")
                # Ensure even length
                if len(hex_str) % 2 == 1:
                    hex_str = "0" + hex_str
                decoded = bytes.fromhex(hex_str).decode("utf-8", errors="ignore")
                if decoded and len(decoded) > 5 and any(c.isalpha() for c in decoded):
                    variants.append(decoded)
                    logger.debug(f"Decoded hex: {decoded[:50]}...")
            except Exception:
                pass

        # 4. Unicode escape decoding (\uXXXX sequences)
        if self.UNICODE_ESCAPE_PATTERN.search(content):
            try:
                # Use codecs to properly decode unicode escapes
                unicode_decoded = content.encode("utf-8").decode("unicode_escape")
                if unicode_decoded != content:
                    variants.append(unicode_decoded)
                    logger.debug(f"Unicode decoded: {unicode_decoded[:50]}...")
            except Exception:
                pass

        return variants

    def _validate_single(self, content: str) -> ValidationResult:
        """Validate a single piece of content (no decoding).

        Args:
            content: The text to validate

        Returns:
            ValidationResult with injection detection results
        """
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

    def validate(self, content: str, **kwargs: Any) -> ValidationResult:
        """Validate content for prompt injection attempts.

        Automatically detects and decodes obfuscated payloads (base64, hex,
        URL encoding, unicode escapes) before validation.

        Args:
            content: The text to validate (user input, prompt, etc.)
            **kwargs: Additional parameters (unused)

        Returns:
            ValidationResult with:
                - success: True if no injection detected (SAFE)
                - score: Safety score (1.0 = safe, 0.0 = injection)
                - details: label, injection_score, safe_score, decoded_variants
        """
        if not content or not content.strip():
            return ValidationResult(
                success=True,
                score=1.0,
                details={"reason": "empty_content"},
            )

        # Decode and get all variants to check
        variants = self._decode_content(content)

        # Check each variant - return first threat found
        for i, variant in enumerate(variants):
            result = self._validate_single(variant)

            # If threat detected, add info about which variant triggered it
            if result.is_threat:
                result.details["decoded_variant_index"] = i
                result.details["decoded_variants_checked"] = len(variants)
                if i > 0:
                    result.details["detected_in_decoded"] = True
                    result.details["original_content"] = content[:100] + "..." if len(content) > 100 else content
                return result

        # If no threat in any variant, return the original content's result
        final_result = self._validate_single(content)
        final_result.details["decoded_variants_checked"] = len(variants)
        return final_result
