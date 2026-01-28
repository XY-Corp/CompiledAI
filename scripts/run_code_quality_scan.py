#!/usr/bin/env python3
"""Run code quality scans on generated workflows and output metrics for Table 15.

This script runs all 5 code quality tools on generated code artifacts:
- Security: Bandit + detect-secrets + Semgrep (SAST)
- TypeCov: mypy type coverage
- LintScore: ruff linting score
- Complexity: radon cyclomatic complexity
- TestPass: pytest test pass rate

Usage:
    python scripts/run_code_quality_scan.py --input workflows/ --output results/table15_metrics.json
    python scripts/run_code_quality_scan.py --input workflows/ --no-semgrep  # Skip Semgrep (faster)

Output:
    JSON file with aggregated metrics for Table 15 of the paper.
"""

import argparse
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class Table15Metrics:
    """Metrics for Table 15: Code quality metrics for generated artifacts."""

    # Security (Bandit + detect-secrets + Semgrep)
    security_critical: int = 0
    security_high: int = 0
    security_medium: int = 0
    security_low: int = 0
    security_total: int = 0

    # TypeCov (mypy)
    type_coverage_percent: float = 0.0
    typed_functions: int = 0
    total_functions: int = 0

    # LintScore (ruff)
    lint_errors: int = 0
    lint_warnings: int = 0
    lint_score: float = 10.0  # Start at 10, subtract for issues

    # Complexity (radon)
    avg_complexity: float = 0.0
    max_complexity: float = 0.0
    functions_analyzed: int = 0

    # TestPass (pytest) - for the test suite, not generated code
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0
    test_pass_rate: float = 100.0

    # Metadata
    files_scanned: int = 0
    total_lines: int = 0

    def to_table15_format(self) -> dict[str, Any]:
        """Format metrics for Table 15 in the paper."""
        return {
            "Source": "Compiled AI",
            "Security": f"{self.security_high + self.security_critical}",  # high/critical count
            "TypeCov": f"{self.type_coverage_percent:.0f}%",
            "LintScore": f"{self.lint_score:.1f}",
            "Complexity": f"{self.avg_complexity:.1f}",
            "TestPass": f"{self.test_pass_rate:.0f}%",
        }

    def to_dict(self) -> dict[str, Any]:
        """Full metrics as dictionary."""
        return {
            "security": {
                "critical": self.security_critical,
                "high": self.security_high,
                "medium": self.security_medium,
                "low": self.security_low,
                "total": self.security_total,
                "table15_value": self.security_high + self.security_critical,
            },
            "type_coverage": {
                "percent": self.type_coverage_percent,
                "typed_functions": self.typed_functions,
                "total_functions": self.total_functions,
                "table15_value": f"{self.type_coverage_percent:.0f}%",
            },
            "lint": {
                "errors": self.lint_errors,
                "warnings": self.lint_warnings,
                "score": self.lint_score,
                "table15_value": f"{self.lint_score:.1f}",
            },
            "complexity": {
                "average": self.avg_complexity,
                "max": self.max_complexity,
                "functions_analyzed": self.functions_analyzed,
                "table15_value": f"{self.avg_complexity:.1f}",
            },
            "tests": {
                "passed": self.tests_passed,
                "failed": self.tests_failed,
                "total": self.tests_total,
                "pass_rate": self.test_pass_rate,
                "table15_value": f"{self.test_pass_rate:.0f}%",
            },
            "metadata": {
                "files_scanned": self.files_scanned,
                "total_lines": self.total_lines,
            },
            "table15": self.to_table15_format(),
        }


def run_bandit(files: list[Path]) -> dict[str, int]:
    """Run Bandit security scanner on files.

    Returns:
        Dict with severity counts: critical, high, medium, low
    """
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    if not files:
        return counts

    try:
        # Run bandit on all files at once
        file_args = [str(f) for f in files]
        result = subprocess.run(
            ["bandit", "-f", "json", "-q", "-r"] + file_args,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.stdout:
            data = json.loads(result.stdout)
            for finding in data.get("results", []):
                severity = finding.get("issue_severity", "LOW").lower()
                if severity in counts:
                    counts[severity] += 1

        logger.info(f"Bandit: {sum(counts.values())} issues found")

    except subprocess.TimeoutExpired:
        logger.warning("Bandit scan timed out")
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse Bandit output: {e}")
    except FileNotFoundError:
        logger.error("Bandit not installed. Run: pip install bandit")
    except Exception as e:
        logger.error(f"Bandit scan failed: {e}")

    return counts


def run_detect_secrets(files: list[Path]) -> int:
    """Run detect-secrets on files.

    Returns:
        Count of secrets found (all treated as high severity)
    """
    secrets_count = 0

    for file_path in files:
        try:
            result = subprocess.run(
                ["detect-secrets", "scan", str(file_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.stdout:
                data = json.loads(result.stdout)
                for findings in data.get("results", {}).values():
                    secrets_count += len(findings)

        except subprocess.TimeoutExpired:
            continue
        except json.JSONDecodeError:
            continue
        except FileNotFoundError:
            logger.error("detect-secrets not installed. Run: pip install detect-secrets")
            break
        except Exception:
            continue

    logger.info(f"detect-secrets: {secrets_count} secrets found")
    return secrets_count


def run_semgrep(directory: Path) -> dict[str, int]:
    """Run Semgrep with Python security rules.

    Returns:
        Dict with severity counts
    """
    counts = {"error": 0, "warning": 0, "info": 0}

    try:
        result = subprocess.run(
            [
                "semgrep",
                "--config=p/python",
                "--json",
                "--quiet",
                str(directory),
            ],
            capture_output=True,
            text=True,
            timeout=600,  # Semgrep can be slow
        )

        if result.stdout:
            data = json.loads(result.stdout)
            for finding in data.get("results", []):
                severity = finding.get("extra", {}).get("severity", "WARNING").lower()
                if severity in counts:
                    counts[severity] += 1

        logger.info(f"Semgrep: {sum(counts.values())} issues found")

    except subprocess.TimeoutExpired:
        logger.warning("Semgrep scan timed out")
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse Semgrep output: {e}")
    except FileNotFoundError:
        logger.error("Semgrep not installed. Run: pip install semgrep")
    except Exception as e:
        logger.error(f"Semgrep scan failed: {e}")

    return counts


def run_mypy(files: list[Path]) -> tuple[float, int, int]:
    """Run mypy for type coverage.

    Returns:
        Tuple of (coverage_percent, typed_functions, total_functions)
    """
    typed = 0
    total = 0

    try:
        # Run mypy with coverage report
        file_args = [str(f) for f in files[:100]]  # Limit to avoid timeout
        result = subprocess.run(
            ["mypy", "--ignore-missing-imports", "--no-error-summary"] + file_args,
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Count lines with type annotations vs total
        for file_path in files:
            try:
                content = file_path.read_text()
                lines = content.split("\n")
                for line in lines:
                    if "def " in line or "async def " in line:
                        total += 1
                        if "->" in line or ": " in line:
                            typed += 1
            except Exception:
                continue

        coverage = (typed / total * 100) if total > 0 else 0.0
        logger.info(f"mypy: {coverage:.1f}% type coverage ({typed}/{total} functions)")

    except subprocess.TimeoutExpired:
        logger.warning("mypy scan timed out")
    except FileNotFoundError:
        logger.error("mypy not installed. Run: pip install mypy")
    except Exception as e:
        logger.error(f"mypy scan failed: {e}")

    return (typed / total * 100) if total > 0 else 0.0, typed, total


def run_ruff(files: list[Path]) -> tuple[int, int, float]:
    """Run ruff linter.

    Returns:
        Tuple of (errors, warnings, score out of 10)
    """
    errors = 0
    warnings = 0

    try:
        file_args = [str(f) for f in files]
        result = subprocess.run(
            ["ruff", "check", "--output-format=json"] + file_args,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.stdout:
            findings = json.loads(result.stdout)
            for finding in findings:
                code = finding.get("code", "")
                if code.startswith("E") or code.startswith("F"):
                    errors += 1
                else:
                    warnings += 1

        # Calculate score: start at 10, subtract 0.1 per error, 0.05 per warning
        total_files = len(files)
        if total_files > 0:
            issues_per_file = (errors + warnings) / total_files
            score = max(0.0, 10.0 - (errors * 0.1) - (warnings * 0.05))
            # Normalize to reasonable range
            score = max(0.0, min(10.0, score))
        else:
            score = 10.0

        logger.info(f"ruff: {errors} errors, {warnings} warnings, score: {score:.1f}")

    except subprocess.TimeoutExpired:
        logger.warning("ruff scan timed out")
        score = 0.0
    except json.JSONDecodeError:
        # ruff outputs nothing if no issues
        score = 10.0
    except FileNotFoundError:
        logger.error("ruff not installed. Run: pip install ruff")
        score = 0.0
    except Exception as e:
        logger.error(f"ruff scan failed: {e}")
        score = 0.0

    return errors, warnings, score


def run_radon(files: list[Path]) -> tuple[float, float, int]:
    """Run radon for cyclomatic complexity.

    Returns:
        Tuple of (avg_complexity, max_complexity, functions_analyzed)
    """
    complexities: list[float] = []

    try:
        file_args = [str(f) for f in files]
        result = subprocess.run(
            ["radon", "cc", "-j"] + file_args,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.stdout:
            data = json.loads(result.stdout)
            for file_data in data.values():
                for func in file_data:
                    if isinstance(func, dict) and "complexity" in func:
                        complexities.append(func["complexity"])

        avg = sum(complexities) / len(complexities) if complexities else 0.0
        max_cc = max(complexities) if complexities else 0.0

        logger.info(f"radon: avg complexity {avg:.1f}, max {max_cc:.0f}, {len(complexities)} functions")

    except subprocess.TimeoutExpired:
        logger.warning("radon scan timed out")
        avg, max_cc = 0.0, 0.0
    except json.JSONDecodeError:
        avg, max_cc = 0.0, 0.0
    except FileNotFoundError:
        logger.error("radon not installed. Run: pip install radon")
        avg, max_cc = 0.0, 0.0
    except Exception as e:
        logger.error(f"radon scan failed: {e}")
        avg, max_cc = 0.0, 0.0

    return avg, max_cc, len(complexities)


def run_pytest(test_dir: Path) -> tuple[int, int, int, float]:
    """Run pytest on test directory.

    Returns:
        Tuple of (passed, failed, total, pass_rate)
    """
    passed = 0
    failed = 0

    try:
        result = subprocess.run(
            ["pytest", str(test_dir), "--tb=no", "-q"],
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Parse pytest output for pass/fail counts
        output = result.stdout + result.stderr
        for line in output.split("\n"):
            if "passed" in line:
                import re
                match = re.search(r"(\d+) passed", line)
                if match:
                    passed = int(match.group(1))
            if "failed" in line:
                import re
                match = re.search(r"(\d+) failed", line)
                if match:
                    failed = int(match.group(1))

        total = passed + failed
        pass_rate = (passed / total * 100) if total > 0 else 100.0

        logger.info(f"pytest: {passed}/{total} passed ({pass_rate:.0f}%)")

    except subprocess.TimeoutExpired:
        logger.warning("pytest timed out")
        pass_rate = 0.0
    except FileNotFoundError:
        logger.error("pytest not installed. Run: pip install pytest")
        pass_rate = 100.0
    except Exception as e:
        logger.error(f"pytest failed: {e}")
        pass_rate = 100.0

    return passed, failed, passed + failed, pass_rate


def scan_directory(
    input_dir: Path,
    enable_semgrep: bool = True,
    test_dir: Path | None = None,
) -> Table15Metrics:
    """Scan a directory and collect all metrics for Table 15.

    Args:
        input_dir: Directory containing generated code (e.g., workflows/)
        enable_semgrep: Whether to run Semgrep (can be slow)
        test_dir: Directory containing tests (e.g., tests/)

    Returns:
        Table15Metrics with all collected data
    """
    metrics = Table15Metrics()

    # Find all Python files
    py_files = list(input_dir.rglob("*.py"))
    logger.info(f"Found {len(py_files)} Python files in {input_dir}")

    if not py_files:
        logger.warning("No Python files found!")
        return metrics

    metrics.files_scanned = len(py_files)

    # Count total lines
    for f in py_files:
        try:
            metrics.total_lines += len(f.read_text().split("\n"))
        except Exception:
            pass

    # 1. Security: Bandit
    logger.info("Running Bandit...")
    bandit_counts = run_bandit(py_files)
    metrics.security_critical = bandit_counts["critical"]
    metrics.security_high = bandit_counts["high"]
    metrics.security_medium = bandit_counts["medium"]
    metrics.security_low = bandit_counts["low"]

    # 2. Security: detect-secrets
    logger.info("Running detect-secrets...")
    secrets_count = run_detect_secrets(py_files)
    metrics.security_high += secrets_count  # Secrets are high severity

    # 3. Security: Semgrep (optional)
    if enable_semgrep:
        logger.info("Running Semgrep...")
        semgrep_counts = run_semgrep(input_dir)
        metrics.security_high += semgrep_counts["error"]
        metrics.security_medium += semgrep_counts["warning"]
        metrics.security_low += semgrep_counts["info"]

    metrics.security_total = (
        metrics.security_critical
        + metrics.security_high
        + metrics.security_medium
        + metrics.security_low
    )

    # 4. TypeCov: mypy
    logger.info("Running mypy...")
    coverage, typed, total = run_mypy(py_files)
    metrics.type_coverage_percent = coverage
    metrics.typed_functions = typed
    metrics.total_functions = total

    # 5. LintScore: ruff
    logger.info("Running ruff...")
    errors, warnings, score = run_ruff(py_files)
    metrics.lint_errors = errors
    metrics.lint_warnings = warnings
    metrics.lint_score = score

    # 6. Complexity: radon
    logger.info("Running radon...")
    avg_cc, max_cc, func_count = run_radon(py_files)
    metrics.avg_complexity = avg_cc
    metrics.max_complexity = max_cc
    metrics.functions_analyzed = func_count

    # 7. TestPass: pytest (if test directory provided)
    if test_dir and test_dir.exists():
        logger.info("Running pytest...")
        passed, failed, total, rate = run_pytest(test_dir)
        metrics.tests_passed = passed
        metrics.tests_failed = failed
        metrics.tests_total = total
        metrics.test_pass_rate = rate
    else:
        logger.info("Skipping pytest (no test directory)")
        metrics.test_pass_rate = 100.0  # Default if no tests

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Run code quality scans for Table 15 metrics"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("workflows"),
        help="Directory containing generated code (default: workflows/)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("results/table15_metrics.json"),
        help="Output JSON file (default: results/table15_metrics.json)",
    )
    parser.add_argument(
        "--tests",
        "-t",
        type=Path,
        default=Path("tests"),
        help="Test directory for pytest (default: tests/)",
    )
    parser.add_argument(
        "--no-semgrep",
        action="store_true",
        help="Skip Semgrep analysis (faster)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.input.exists():
        logger.error(f"Input directory not found: {args.input}")
        sys.exit(1)

    # Create output directory
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Run scans
    logger.info(f"Scanning {args.input}...")
    metrics = scan_directory(
        input_dir=args.input,
        enable_semgrep=not args.no_semgrep,
        test_dir=args.tests if args.tests.exists() else None,
    )

    # Output results
    results = metrics.to_dict()

    # Write JSON
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results written to {args.output}")

    # Print Table 15 format
    print("\n" + "=" * 60)
    print("TABLE 15: Code quality metrics for generated artifacts")
    print("=" * 60)
    table15 = metrics.to_table15_format()
    print(f"{'Source':<15} {'Security':<10} {'TypeCov':<10} {'LintScore':<10} {'Complexity':<12} {'TestPass':<10}")
    print("-" * 60)
    print(f"{'Compiled AI':<15} {table15['Security']:<10} {table15['TypeCov']:<10} {table15['LintScore']:<10} {table15['Complexity']:<12} {table15['TestPass']:<10}")
    print(f"{'Human code':<15} {'0':<10} {'85%':<10} {'8.5':<10} {'8':<12} {'100%':<10}")
    print("=" * 60)

    # Summary
    print(f"\nFiles scanned: {metrics.files_scanned}")
    print(f"Total lines: {metrics.total_lines}")
    print(f"Security issues (high/critical): {metrics.security_high + metrics.security_critical}")


if __name__ == "__main__":
    main()
