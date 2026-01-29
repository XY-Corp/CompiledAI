"""Static Application Security Testing (SAST) for generated code.

This module provides SAST validation using:
- Bandit: Python security linter (SQL injection, command injection, hardcoded passwords)
- detect-secrets: Finds hardcoded API keys, tokens, credentials
- Semgrep: OWASP rules and broader vulnerability patterns (optional)

References:
- Bandit: https://bandit.readthedocs.io/
- detect-secrets: https://github.com/Yelp/detect-secrets
- Semgrep: https://semgrep.dev/
- Paper Section 3.4: Stage 1 Security Validation
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import ValidationResult, Validator, register_validator

logger = logging.getLogger(__name__)


@dataclass
class SASTIssue:
    """A single SAST finding."""

    tool: str  # "bandit", "detect-secrets", "semgrep"
    severity: str  # "low", "medium", "high", "critical"
    confidence: str  # "low", "medium", "high"
    rule_id: str  # e.g., "B101", "B608"
    message: str
    line: int = 0
    column: int = 0
    cwe_id: str | None = None


@dataclass
class SASTResult:
    """Aggregated SAST scan results."""

    issues: list[SASTIssue] = field(default_factory=list)
    bandit_issues: int = 0
    secrets_issues: int = 0
    semgrep_issues: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def has_blocking_issues(self) -> bool:
        """Returns True if there are high or critical severity issues."""
        return self.critical_count > 0 or self.high_count > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_issues": self.total_issues,
            "bandit_issues": self.bandit_issues,
            "secrets_issues": self.secrets_issues,
            "semgrep_issues": self.semgrep_issues,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "issues": [
                {
                    "tool": i.tool,
                    "severity": i.severity,
                    "confidence": i.confidence,
                    "rule_id": i.rule_id,
                    "message": i.message,
                    "line": i.line,
                    "cwe_id": i.cwe_id,
                }
                for i in self.issues
            ],
        }


@register_validator("sast")
class SASTValidator(Validator):
    """Static Application Security Testing validator for generated code.

    Runs Bandit, detect-secrets, and optionally Semgrep on code to detect
    security vulnerabilities before execution.

    Attributes:
        severity_threshold: Minimum severity to fail ("low", "medium", "high", "critical")
        enable_semgrep: Whether to run Semgrep (can be slow, optional)
        semgrep_config: Semgrep ruleset config (default: "p/python")

    Example:
        validator = SASTValidator(severity_threshold="high")
        result = validator.validate(generated_code)
        if result.is_threat:
            print(f"Security issues: {result.details['issues']}")
    """

    def __init__(
        self,
        severity_threshold: str = "high",
        enable_semgrep: bool = True,
        semgrep_config: str = "p/python",
    ):
        """Initialize the SAST validator.

        Args:
            severity_threshold: Minimum severity to fail validation
            enable_semgrep: Whether to run Semgrep analysis
            semgrep_config: Semgrep ruleset (e.g., "p/python", "p/owasp-top-ten")
        """
        self.severity_threshold = severity_threshold.lower()
        self.enable_semgrep = enable_semgrep
        self.semgrep_config = semgrep_config
        self._severity_order = ["low", "medium", "high", "critical"]

    def _severity_meets_threshold(self, severity: str) -> bool:
        """Check if severity meets or exceeds threshold."""
        try:
            threshold_idx = self._severity_order.index(self.severity_threshold)
            severity_idx = self._severity_order.index(severity.lower())
            return severity_idx >= threshold_idx
        except ValueError:
            return False

    def _run_bandit(self, code_path: Path) -> list[SASTIssue]:
        """Run Bandit security linter on code.

        Args:
            code_path: Path to Python file to scan

        Returns:
            List of SASTIssue findings
        """
        issues: list[SASTIssue] = []
        try:
            result = subprocess.run(
                ["bandit", "-f", "json", "-q", str(code_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.stdout:
                data = json.loads(result.stdout)
                for finding in data.get("results", []):
                    issues.append(
                        SASTIssue(
                            tool="bandit",
                            severity=finding.get("issue_severity", "low").lower(),
                            confidence=finding.get("issue_confidence", "low").lower(),
                            rule_id=finding.get("test_id", ""),
                            message=finding.get("issue_text", ""),
                            line=finding.get("line_number", 0),
                            cwe_id=finding.get("issue_cwe", {}).get("id"),
                        )
                    )
        except subprocess.TimeoutExpired:
            logger.warning("Bandit scan timed out")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Bandit output: {e}")
        except FileNotFoundError:
            logger.warning("Bandit not installed")
        except Exception as e:
            logger.error(f"Bandit scan failed: {e}")

        return issues

    def _run_detect_secrets(self, code_path: Path) -> list[SASTIssue]:
        """Run detect-secrets to find hardcoded credentials.

        Args:
            code_path: Path to file to scan

        Returns:
            List of SASTIssue findings
        """
        issues: list[SASTIssue] = []
        try:
            result = subprocess.run(
                ["detect-secrets", "scan", str(code_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.stdout:
                data = json.loads(result.stdout)
                for file_path, findings in data.get("results", {}).items():
                    for finding in findings:
                        issues.append(
                            SASTIssue(
                                tool="detect-secrets",
                                severity="high",  # Secrets are always high severity
                                confidence="high",
                                rule_id=finding.get("type", "Secret"),
                                message=f"Potential secret detected: {finding.get('type', 'unknown')}",
                                line=finding.get("line_number", 0),
                            )
                        )
        except subprocess.TimeoutExpired:
            logger.warning("detect-secrets scan timed out")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse detect-secrets output: {e}")
        except FileNotFoundError:
            logger.warning("detect-secrets not installed")
        except Exception as e:
            logger.error(f"detect-secrets scan failed: {e}")

        return issues

    def _run_semgrep(self, code_path: Path) -> list[SASTIssue]:
        """Run Semgrep with security rules.

        Args:
            code_path: Path to file to scan

        Returns:
            List of SASTIssue findings
        """
        issues: list[SASTIssue] = []
        try:
            result = subprocess.run(
                [
                    "semgrep",
                    "--config",
                    self.semgrep_config,
                    "--json",
                    "--quiet",
                    str(code_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,  # Semgrep can be slower
            )

            if result.stdout:
                data = json.loads(result.stdout)
                for finding in data.get("results", []):
                    # Map Semgrep severity to our scale
                    semgrep_severity = finding.get("extra", {}).get("severity", "WARNING")
                    severity_map = {
                        "ERROR": "high",
                        "WARNING": "medium",
                        "INFO": "low",
                    }
                    severity = severity_map.get(semgrep_severity.upper(), "medium")

                    issues.append(
                        SASTIssue(
                            tool="semgrep",
                            severity=severity,
                            confidence="high",  # Semgrep rules are generally high confidence
                            rule_id=finding.get("check_id", ""),
                            message=finding.get("extra", {}).get("message", ""),
                            line=finding.get("start", {}).get("line", 0),
                            column=finding.get("start", {}).get("col", 0),
                            cwe_id=finding.get("extra", {}).get("metadata", {}).get("cwe"),
                        )
                    )
        except subprocess.TimeoutExpired:
            logger.warning("Semgrep scan timed out")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Semgrep output: {e}")
        except FileNotFoundError:
            logger.warning("Semgrep not installed")
        except Exception as e:
            logger.error(f"Semgrep scan failed: {e}")

        return issues

    def scan_file(self, file_path: Path) -> SASTResult:
        """Scan a file with all SAST tools.

        Args:
            file_path: Path to Python file to scan

        Returns:
            SASTResult with aggregated findings
        """
        result = SASTResult()

        # Run Bandit
        bandit_issues = self._run_bandit(file_path)
        result.bandit_issues = len(bandit_issues)
        result.issues.extend(bandit_issues)

        # Run detect-secrets
        secrets_issues = self._run_detect_secrets(file_path)
        result.secrets_issues = len(secrets_issues)
        result.issues.extend(secrets_issues)

        # Run Semgrep (optional)
        if self.enable_semgrep:
            semgrep_issues = self._run_semgrep(file_path)
            result.semgrep_issues = len(semgrep_issues)
            result.issues.extend(semgrep_issues)

        # Count by severity
        for issue in result.issues:
            if issue.severity == "critical":
                result.critical_count += 1
            elif issue.severity == "high":
                result.high_count += 1
            elif issue.severity == "medium":
                result.medium_count += 1
            else:
                result.low_count += 1

        return result

    def scan_code(self, code: str) -> SASTResult:
        """Scan code string with all SAST tools.

        Creates a temporary file to run the tools.

        Args:
            code: Python code string to scan

        Returns:
            SASTResult with aggregated findings
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp_file:
            tmp_file.write(code)
            tmp_path = Path(tmp_file.name)

        try:
            return self.scan_file(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def validate(self, content: str, **kwargs: Any) -> ValidationResult:
        """Validate code for security vulnerabilities.

        Args:
            content: Python code string to validate
            **kwargs: Additional parameters (unused)

        Returns:
            ValidationResult with:
                - success: True if no issues meeting threshold found
                - score: Safety score based on issue count/severity
                - details: Full SAST results including all issues
        """
        if not content or not content.strip():
            return ValidationResult(
                success=True,
                score=1.0,
                details={"method": "sast", "reason": "empty_content"},
            )

        # Run SAST scan
        sast_result = self.scan_code(content)

        # Filter issues by severity threshold
        blocking_issues = [
            issue
            for issue in sast_result.issues
            if self._severity_meets_threshold(issue.severity)
        ]

        # Calculate score (1.0 = safe, 0.0 = many issues)
        if not sast_result.issues:
            score = 1.0
        else:
            score = 1.0
            for issue in sast_result.issues:
                if issue.severity == "critical":
                    score -= 0.4
                elif issue.severity == "high":
                    score -= 0.2
                elif issue.severity == "medium":
                    score -= 0.1
                else:
                    score -= 0.05
            score = max(0.0, score)

        is_safe = len(blocking_issues) == 0

        return ValidationResult(
            success=is_safe,
            score=score,
            details={
                "method": "sast",
                "severity_threshold": self.severity_threshold,
                "blocking_issues": len(blocking_issues),
                **sast_result.to_dict(),
            },
        )


def scan_directory(
    directory: Path,
    pattern: str = "*.py",
    enable_semgrep: bool = True,
    severity_threshold: str = "high",
) -> dict[str, SASTResult]:
    """Scan all Python files in a directory.

    Args:
        directory: Directory to scan
        pattern: Glob pattern for files (default: "*.py")
        enable_semgrep: Whether to run Semgrep
        severity_threshold: Minimum severity to report

    Returns:
        Dict mapping file paths to SASTResult
    """
    validator = SASTValidator(
        severity_threshold=severity_threshold,
        enable_semgrep=enable_semgrep,
    )

    results: dict[str, SASTResult] = {}
    for file_path in directory.rglob(pattern):
        logger.info(f"Scanning {file_path}")
        results[str(file_path)] = validator.scan_file(file_path)

    return results
