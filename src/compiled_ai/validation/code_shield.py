"""Code safety validation using Meta's CodeShield.

This module validates LLM-generated code for security vulnerabilities
using Meta's CodeShield library (pip install codeshield).

CodeShield uses:
- Regex-based pattern detection for common vulnerabilities
- Semgrep rules for deeper static analysis

References:
- Meta Code Shield: https://github.com/meta-llama/PurpleLlama/tree/main/CodeShield
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import ValidationResult, Validator, register_validator

logger = logging.getLogger(__name__)


@register_validator("code_shield")
class CodeShieldValidator(Validator):
    """Validates generated code for security vulnerabilities using Meta's CodeShield.

    Uses Meta's CodeShield library which provides:
    - Regex-based pattern detection (MD5, SHA1, hardcoded secrets, etc.)
    - Semgrep rules for deeper analysis (SQL injection, command injection, etc.)

    Attributes:
        severity_threshold: Minimum severity to fail ("low", "medium", "high", "critical", "warning")

    Example:
        validator = CodeShieldValidator(severity_threshold="high")
        result = validator.validate(generated_code)
        if result.is_threat:
            print(f"Security issues: {result.details['issues']}")
    """

    def __init__(
        self,
        severity_threshold: str = "warning",
    ):
        """Initialize the CodeShield validator.

        Args:
            severity_threshold: Minimum severity to fail validation
        """
        self.severity_threshold = severity_threshold
        self._severity_order = ["low", "medium", "warning", "high", "critical"]

    def _severity_meets_threshold(self, severity: str) -> bool:
        """Check if severity meets or exceeds threshold."""
        try:
            threshold_idx = self._severity_order.index(self.severity_threshold.lower())
            severity_idx = self._severity_order.index(severity.lower())
            return severity_idx >= threshold_idx
        except ValueError:
            return False

    async def _scan_code(self, code: str, language: str = "python") -> dict[str, Any]:
        """Scan code using CodeShield.

        Args:
            code: Source code to analyze
            language: Programming language

        Returns:
            Dict with scan results
        """
        try:
            from codeshield.cs import CodeShield, Language

            # Map language string to enum
            lang_map = {
                "python": Language.PYTHON,
                "javascript": Language.JAVASCRIPT,
                "java": Language.JAVA,
                "c": Language.C,
                "cpp": Language.CPP,
                "rust": Language.RUST,
                "ruby": Language.RUBY,
                "php": Language.PHP,
            }
            lang_enum = lang_map.get(language.lower(), Language.PYTHON)

            result = await CodeShield.scan_code(code, lang_enum)

            issues = []
            if result.issues_found:
                for issue in result.issues_found:
                    issues.append(
                        {
                            "type": "codeshield",
                            "severity": issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity),
                            "line": issue.line or 0,
                            "cwe_id": issue.cwe_id,
                            "pattern_id": issue.pattern_id,
                            "message": issue.description,
                        }
                    )

            return {
                "success": True,
                "is_insecure": result.is_insecure,
                "issues": issues,
                "treatment": str(result.recommended_treatment) if result.recommended_treatment else None,
            }

        except ImportError as e:
            logger.error(f"CodeShield not installed: {e}")
            return {
                "success": False,
                "error": "codeshield_not_installed",
                "issues": [],
            }
        except Exception as e:
            logger.error(f"CodeShield analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "issues": [],
            }

    def validate(self, content: str, language: str = "python", **kwargs: Any) -> ValidationResult:
        """Validate code for security vulnerabilities.

        Args:
            content: Source code to validate
            language: Programming language (default: python)
            **kwargs: Additional parameters (unused)

        Returns:
            ValidationResult with:
                - success: True if no issues meeting threshold found
                - score: Safety score based on issue count/severity
                - details: Full analysis results including all issues
        """
        if not content or not content.strip():
            return ValidationResult(
                success=True,
                score=1.0,
                details={"method": "skip", "reason": "empty_content"},
            )

        # Run async CodeShield in sync context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(self._scan_code(content, language))

        if not result["success"]:
            return ValidationResult(
                success=False,
                score=0.0,
                details={
                    "method": "code_shield",
                    "error": result.get("error"),
                },
                error=result.get("error"),
            )

        all_issues = result.get("issues", [])

        # Filter issues by severity threshold
        blocking_issues = [
            issue
            for issue in all_issues
            if self._severity_meets_threshold(issue.get("severity", "low"))
        ]

        # Calculate score
        if not all_issues:
            score = 1.0
        else:
            score = 1.0
            for issue in all_issues:
                severity = issue.get("severity", "low").lower()
                if severity == "critical":
                    score -= 0.4
                elif severity == "high":
                    score -= 0.2
                elif severity in ["medium", "warning"]:
                    score -= 0.1
                else:
                    score -= 0.05
            score = max(0.0, score)

        is_safe = len(blocking_issues) == 0

        return ValidationResult(
            success=is_safe,
            score=score,
            details={
                "method": "code_shield",
                "is_insecure": result.get("is_insecure", False),
                "total_issues": len(all_issues),
                "blocking_issues": len(blocking_issues),
                "issues": all_issues,
                "treatment": result.get("treatment"),
                "severity_threshold": self.severity_threshold,
            },
        )
