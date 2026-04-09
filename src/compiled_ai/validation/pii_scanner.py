"""PII (Personally Identifiable Information) scanning using LLM-Guard + regex patterns.

This module detects and optionally redacts PII from text to ensure
GDPR/SOC2 compliance before sending data to external LLMs.

Uses a hybrid approach:
1. LLM-Guard NER-based detection for common entities (names, emails, SSN, etc.)
2. Regex-based detection for specialized patterns (crypto wallets, API keys, etc.)

References:
- LLM-Guard Anonymize: https://llm-guard.com/input_scanners/anonymize/
- GDPR Article 4: Definition of personal data
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .base import ValidationResult, Validator, register_validator

logger = logging.getLogger(__name__)


# Additional PII patterns not covered by NER models
ADDITIONAL_PII_PATTERNS = {
    # Tax IDs
    "ein": re.compile(r"\b\d{2}-\d{7}\b"),  # US Employer ID: 12-3456789
    "australian_tfn": re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\b"),  # Australian TFN
    "canadian_sin": re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}\b"),  # Canadian SIN

    # Crypto wallets
    "bitcoin_wallet": re.compile(r"\b(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,39}\b"),
    "ethereum_wallet": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),

    # Network identifiers
    "mac_address": re.compile(r"\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b"),
    "ipv6": re.compile(r"\b([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"),

    # Credentials & secrets
    "connection_string": re.compile(
        r"(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@[^\s]+"
    ),
    "url_with_credentials": re.compile(
        r"https?://[^:]+:[^@]+@[^\s]+"
    ),
    "private_key_header": re.compile(
        r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"
    ),
    "jwt_token": re.compile(
        r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
    ),

    # API keys & webhooks
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "aws_secret_key": re.compile(r"\b[A-Za-z0-9/+=]{40}\b"),  # Broad pattern, may have FPs
    "slack_webhook": re.compile(
        r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+"
    ),
    "github_token": re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"),
    "stripe_key": re.compile(r"\b(sk|pk)_(test|live)_[A-Za-z0-9]{24,}\b"),

    # Identity documents
    "drivers_license_ca": re.compile(r"\b[A-Z]\d{7}\b"),  # California: D1234567
    "passport_number": re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),  # Generic passport
    "medical_record": re.compile(r"\bMRN[-:]?\s*\d{6,}\b", re.IGNORECASE),
}


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

    def _check_additional_patterns(self, content: str) -> dict[str, list[str]]:
        """Check content against additional regex patterns.

        Returns:
            Dict mapping pattern names to list of matches found
        """
        matches: dict[str, list[str]] = {}
        for pattern_name, pattern in ADDITIONAL_PII_PATTERNS.items():
            found = pattern.findall(content)
            if found:
                # Flatten tuples from groups if present
                flattened = []
                for match in found:
                    if isinstance(match, tuple):
                        flattened.append("".join(match))
                    else:
                        flattened.append(match)
                matches[pattern_name] = flattened
        return matches

    def validate(self, content: str, **kwargs: Any) -> ValidationResult:
        """Validate content for PII.

        Uses hybrid approach: NER-based detection + regex patterns for
        specialized PII types (crypto wallets, API keys, connection strings).

        Args:
            content: Text to scan for PII
            **kwargs: Additional parameters (unused)

        Returns:
            ValidationResult with:
                - success: True if no PII found OR PII was sanitized
                - score: Risk score (1.0 = no PII, lower = more PII)
                - details: sanitized_prompt, risk_score, is_valid, regex_matches
        """
        if not content or not content.strip():
            return ValidationResult(
                success=True,
                score=1.0,
                details={"reason": "empty_content"},
            )

        # Run NER-based scanner
        scanner = self._get_scanner()
        sanitized_prompt, is_valid, risk_score = scanner.scan(content)

        # Check if NER found PII
        ner_pii_found = sanitized_prompt != content

        # Run additional regex patterns
        regex_matches = self._check_additional_patterns(content)
        regex_pii_found = len(regex_matches) > 0

        # Combined result: PII found if either detector found something
        pii_found = ner_pii_found or regex_pii_found

        # Adjust risk score if regex found additional PII
        if regex_pii_found and not ner_pii_found:
            # Regex found PII that NER missed - set risk score
            risk_score = max(risk_score, 0.7)
            is_valid = False  # Flag as containing PII

        return ValidationResult(
            success=is_valid,
            score=1.0 - risk_score,
            details={
                "is_valid": is_valid,
                "risk_score": risk_score,
                "has_pii": pii_found,
                "ner_pii_found": ner_pii_found,
                "regex_pii_found": regex_pii_found,
                "regex_matches": regex_matches,
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
