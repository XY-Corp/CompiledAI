"""PII (Personally Identifiable Information) scanning using LLM-Guard.

This module detects and optionally redacts PII from text to ensure
GDPR/SOC2 compliance before sending data to external LLMs.

References:
- LLM-Guard Anonymize: https://llm-guard.com/input_scanners/anonymize/
- GDPR Article 4: Definition of personal data
"""

from __future__ import annotations

import logging
from typing import Any

from .base import ValidationResult, Validator, register_validator

logger = logging.getLogger(__name__)


@register_validator("pii_scanner")
class PIIScanner(Validator):
    """Scans text for Personally Identifiable Information using LLM-Guard.

    Uses BERT-based NER models to detect PII including:
    - Names, emails, phone numbers
    - SSN, credit cards, bank accounts
    - Addresses, dates of birth
    - And more entity types

    Attributes:
        use_faker: Replace PII with fake data instead of [REDACTED]
        allowed_names: Names to NOT redact
        hidden_names: Names to always redact with custom format
        language: Language for NER model ("en" or "zh")

    Example:
        scanner = PIIScanner()
        result = scanner.validate("Contact john@example.com")
        if result.is_threat:
            print(f"PII found! Sanitized: {result.details['sanitized_prompt']}")
    """

    def __init__(
        self,
        use_faker: bool = False,
        allowed_names: list[str] | None = None,
        hidden_names: list[str] | None = None,
        language: str = "en",
        threshold: float = 0.5,
    ):
        """Initialize the PII scanner.

        Args:
            use_faker: If True, replace PII with fake data; otherwise use [REDACTED]
            allowed_names: List of names to NOT redact
            hidden_names: List of names to always redact with [REDACTED_CUSTOM_N]
            language: Language for NER ("en" or "zh")
            threshold: Confidence threshold for entity recognition
        """
        self.use_faker = use_faker
        self.allowed_names = allowed_names or []
        self.hidden_names = hidden_names or []
        self.language = language
        self.threshold = threshold
        self._scanner = None
        self._vault = None

    def _get_scanner(self) -> Any:
        """Lazy-load the LLM-Guard Anonymize scanner."""
        if self._scanner is None:
            from llm_guard.input_scanners import Anonymize
            from llm_guard.vault import Vault

            # Vault stores PII mappings for potential de-anonymization
            self._vault = Vault()

            self._scanner = Anonymize(
                vault=self._vault,
                allowed_names=self.allowed_names,
                hidden_names=self.hidden_names,
                language=self.language,
                use_faker=self.use_faker,
            )
            logger.info("LLM-Guard Anonymize scanner loaded")
        return self._scanner

    def validate(self, content: str, **kwargs: Any) -> ValidationResult:
        """Validate content for PII.

        Args:
            content: Text to scan for PII
            **kwargs: Additional parameters (unused)

        Returns:
            ValidationResult with:
                - success: True if no PII found OR PII was sanitized
                - score: Risk score (1.0 = no PII, lower = more PII)
                - details: sanitized_prompt, risk_score, is_valid
        """
        if not content or not content.strip():
            return ValidationResult(
                success=True,
                score=1.0,
                details={"reason": "empty_content"},
            )

        scanner = self._get_scanner()
        sanitized_prompt, is_valid, risk_score = scanner.scan(content)

        # Check if any PII was found by comparing original vs sanitized
        pii_found = sanitized_prompt != content

        return ValidationResult(
            success=is_valid,
            score=1.0 - risk_score,
            details={
                "is_valid": is_valid,
                "risk_score": risk_score,
                "has_pii": pii_found,
                "sanitized_prompt": sanitized_prompt,
                "original_length": len(content),
                "sanitized_length": len(sanitized_prompt),
            },
        )

    def sanitize(self, content: str) -> tuple[str, dict[str, str]]:
        """Sanitize text by redacting PII.

        Convenience method that returns sanitized text and the vault mappings.

        Args:
            content: Text to sanitize

        Returns:
            Tuple of (sanitized_text, pii_mappings)
        """
        scanner = self._get_scanner()
        sanitized_prompt, _, _ = scanner.scan(content)

        # Get mappings from vault for potential de-anonymization
        pii_map: dict[str, str] = {}
        if self._vault:
            # Vault stores the mappings internally
            pii_map = dict(self._vault.get_all()) if hasattr(self._vault, "get_all") else {}

        return sanitized_prompt, pii_map
