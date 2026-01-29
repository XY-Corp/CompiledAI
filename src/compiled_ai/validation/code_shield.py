"""Comprehensive code safety validation using multiple security tools.

This module validates LLM-generated code for security vulnerabilities
using a combination of static analysis tools:

Tools:
- Bandit: Python SAST for common security issues
- detect-secrets: Hardcoded credentials and secrets detection
- Semgrep: OWASP security rules and pattern matching
- CodeShield: Meta's LLM code validator (regex + Semgrep rules)

References:
- Bandit: https://bandit.readthedocs.io/
- detect-secrets: https://github.com/Yelp/detect-secrets
- Semgrep: https://semgrep.dev/
- CodeShield: https://github.com/meta-llama/PurpleLlama/tree/main/CodeShield
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import ValidationResult, Validator, register_validator

logger = logging.getLogger(__name__)


@register_validator("code_shield")
class CodeShieldValidator(Validator):
    """Comprehensive code safety validator using multiple security tools.

    Runs 4 security tools and aggregates findings:
    - Bandit: Python SAST for common security issues
    - detect-secrets: Hardcoded credentials and secrets detection
    - Semgrep: OWASP security rules and pattern matching
    - CodeShield: Meta's LLM code validator (regex + Semgrep rules)

    Severity levels (normalized): HIGH, MEDIUM, LOW
    - CRITICAL → HIGH
    - WARNING/INFO → LOW

    Attributes:
        severity_threshold: Minimum severity to fail ("low", "medium", "high")

    Example:
        validator = CodeShieldValidator(severity_threshold="high")
        result = validator.validate(generated_code)
        if not result.success:
            print(f"Security issues: {result.details['issues']}")
    """

    def __init__(
        self,
        severity_threshold: str = "low",
    ):
        """Initialize the CodeShield validator.

        Args:
            severity_threshold: Minimum severity to fail validation ("low", "medium", "high")
        """
        self.severity_threshold = severity_threshold.lower()
        self._severity_order = ["low", "medium", "high"]

    def _normalize_severity(self, severity: str) -> str:
        """Normalize severity to HIGH/MEDIUM/LOW."""
        severity = severity.lower()
        if severity in ["critical", "high", "error"]:
            return "high"
        elif severity in ["medium"]:
            return "medium"
        else:  # low, warning, info, or unknown
            return "low"

    def _severity_meets_threshold(self, severity: str) -> bool:
        """Check if severity meets or exceeds threshold."""
        try:
            normalized = self._normalize_severity(severity)
            threshold_idx = self._severity_order.index(self.severity_threshold)
            severity_idx = self._severity_order.index(normalized)
            return severity_idx >= threshold_idx
        except ValueError:
            return False

    def _run_bandit(self, file_path: Path) -> list[dict[str, Any]]:
        """Run Bandit security scanner on a file.

        Args:
            file_path: Path to the Python file to scan

        Returns:
            List of issues found, each with type, severity, line, message
        """
        issues: list[dict[str, Any]] = []

        try:
            result = subprocess.run(
                ["bandit", "-f", "json", "-q", str(file_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.stdout:
                data = json.loads(result.stdout)
                for finding in data.get("results", []):
                    issues.append({
                        "tool": "bandit",
                        "severity": self._normalize_severity(finding.get("issue_severity", "LOW")),
                        "line": finding.get("line_number", 0),
                        "message": finding.get("issue_text", ""),
                        "code": finding.get("test_id", ""),
                    })

        except subprocess.TimeoutExpired:
            logger.warning(f"Bandit scan timed out for {file_path}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Bandit output: {e}")
        except FileNotFoundError:
            logger.debug("Bandit not installed, skipping")
        except Exception as e:
            logger.warning(f"Bandit scan failed: {e}")

        return issues

    def _run_detect_secrets(self, file_path: Path) -> list[dict[str, Any]]:
        """Run detect-secrets on a file.

        Args:
            file_path: Path to the file to scan

        Returns:
            List of issues found (all secrets are HIGH severity)
        """
        issues: list[dict[str, Any]] = []

        try:
            result = subprocess.run(
                ["detect-secrets", "scan", str(file_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.stdout:
                data = json.loads(result.stdout)
                for filename, findings in data.get("results", {}).items():
                    for finding in findings:
                        issues.append({
                            "tool": "detect-secrets",
                            "severity": "high",  # All secrets are high severity
                            "line": finding.get("line_number", 0),
                            "message": f"Potential secret: {finding.get('type', 'unknown')}",
                            "code": finding.get("type", ""),
                        })

        except subprocess.TimeoutExpired:
            logger.warning(f"detect-secrets scan timed out for {file_path}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse detect-secrets output: {e}")
        except FileNotFoundError:
            logger.debug("detect-secrets not installed, skipping")
        except Exception as e:
            logger.warning(f"detect-secrets scan failed: {e}")

        return issues

    def _run_semgrep(self, file_path: Path) -> list[dict[str, Any]]:
        """Run Semgrep with Python security rules on a file.

        Uses both standard p/python rules and custom rules for additional
        vulnerability patterns (dynamic import, path traversal, regex DoS,
        template injection, open redirect).

        Args:
            file_path: Path to the file to scan

        Returns:
            List of issues found
        """
        issues: list[dict[str, Any]] = []

        # Custom rules file path (relative to this module)
        custom_rules = Path(__file__).parent / "semgrep_rules.yaml"

        try:
            # Build semgrep command with both standard and custom rules
            cmd = [
                "semgrep",
                "--config=p/python",
                "--json",
                "--quiet",
                str(file_path),
            ]
            # Add custom rules if they exist
            if custom_rules.exists():
                cmd.insert(2, f"--config={custom_rules}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.stdout:
                data = json.loads(result.stdout)
                for finding in data.get("results", []):
                    raw_severity = finding.get("extra", {}).get("severity", "WARNING")
                    issues.append({
                        "tool": "semgrep",
                        "severity": self._normalize_severity(raw_severity),
                        "line": finding.get("start", {}).get("line", 0),
                        "message": finding.get("extra", {}).get("message", ""),
                        "code": finding.get("check_id", ""),
                    })

        except subprocess.TimeoutExpired:
            logger.warning(f"Semgrep scan timed out for {file_path}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Semgrep output: {e}")
        except FileNotFoundError:
            logger.debug("Semgrep not installed, skipping")
        except Exception as e:
            logger.warning(f"Semgrep scan failed: {e}")

        return issues

    def _run_codeshield(self, code: str, language: str = "python") -> list[dict[str, Any]]:
        """Run CodeShield on code content.

        Args:
            code: Source code to analyze
            language: Programming language

        Returns:
            List of issues found with normalized severity
        """
        issues: list[dict[str, Any]] = []

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

            # Run async CodeShield in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            result = loop.run_until_complete(CodeShield.scan_code(code, lang_enum))

            if result.issues_found:
                for issue in result.issues_found:
                    raw_severity = issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity)
                    issues.append({
                        "tool": "codeshield",
                        "severity": self._normalize_severity(raw_severity),
                        "line": issue.line or 0,
                        "message": issue.description or "",
                        "code": issue.pattern_id or issue.cwe_id or "",
                    })

        except ImportError:
            logger.debug("CodeShield not installed, skipping")
        except Exception as e:
            logger.warning(f"CodeShield scan failed: {e}")

        return issues

    def validate(self, content: str, language: str = "python", **kwargs: Any) -> ValidationResult:
        """Validate code for security vulnerabilities using all 4 tools.

        Runs Bandit, detect-secrets, Semgrep, and CodeShield, then aggregates
        all findings into a unified result.

        Args:
            content: Source code to validate
            language: Programming language (default: python)
            **kwargs: Additional parameters (unused)

        Returns:
            ValidationResult with:
                - success: True if no issues meeting threshold found
                - score: Safety score based on issue count/severity
                - details: Full analysis results including all issues by tool
        """
        if not content or not content.strip():
            return ValidationResult(
                success=True,
                score=1.0,
                details={"method": "skip", "reason": "empty_content"},
            )

        all_issues: list[dict[str, Any]] = []
        tools_run: list[str] = []

        # Write content to temp file for file-based tools
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp_file:
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)

        try:
            # 1. Run Bandit
            bandit_issues = self._run_bandit(tmp_path)
            all_issues.extend(bandit_issues)
            if bandit_issues:
                tools_run.append("bandit")
                logger.debug(f"Bandit found {len(bandit_issues)} issues")

            # 2. Run detect-secrets
            secrets_issues = self._run_detect_secrets(tmp_path)
            all_issues.extend(secrets_issues)
            if secrets_issues:
                tools_run.append("detect-secrets")
                logger.debug(f"detect-secrets found {len(secrets_issues)} issues")

            # 3. Run Semgrep
            semgrep_issues = self._run_semgrep(tmp_path)
            all_issues.extend(semgrep_issues)
            if semgrep_issues:
                tools_run.append("semgrep")
                logger.debug(f"Semgrep found {len(semgrep_issues)} issues")

            # 4. Run CodeShield
            codeshield_issues = self._run_codeshield(content, language)
            all_issues.extend(codeshield_issues)
            if codeshield_issues:
                tools_run.append("codeshield")
                logger.debug(f"CodeShield found {len(codeshield_issues)} issues")

        finally:
            # Clean up temp file
            try:
                tmp_path.unlink()
            except Exception:
                pass

        # Count by severity
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for issue in all_issues:
            severity = issue.get("severity", "low")
            if severity in severity_counts:
                severity_counts[severity] += 1

        # Filter issues by severity threshold
        blocking_issues = [
            issue
            for issue in all_issues
            if self._severity_meets_threshold(issue.get("severity", "low"))
        ]

        # Calculate score (1.0 = safe, 0.0 = unsafe)
        if not all_issues:
            score = 1.0
        else:
            score = 1.0
            for issue in all_issues:
                severity = issue.get("severity", "low")
                if severity == "high":
                    score -= 0.2
                elif severity == "medium":
                    score -= 0.1
                else:  # low
                    score -= 0.05
            score = max(0.0, score)

        is_safe = len(blocking_issues) == 0

        return ValidationResult(
            success=is_safe,
            score=score,
            details={
                "method": "comprehensive_security_scan",
                "tools": ["bandit", "detect-secrets", "semgrep", "codeshield"],
                "tools_with_findings": tools_run,
                "total_issues": len(all_issues),
                "blocking_issues": len(blocking_issues),
                "severity_counts": severity_counts,
                "issues": all_issues,
                "severity_threshold": self.severity_threshold,
            },
        )
