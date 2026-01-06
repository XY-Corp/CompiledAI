"""Structured logging utilities using rich."""

import logging
import os
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Custom theme for benchmark output
BENCHMARK_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "success": "green",
        "metric": "magenta",
        "token": "blue",
        "latency": "yellow",
    }
)

console = Console(theme=BENCHMARK_THEME)


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """Get a logger with rich formatting.

    Args:
        name: Logger name (typically __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to LOG_LEVEL env var or INFO.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        level_str = level or os.getenv("LOG_LEVEL", "INFO")
        log_level = getattr(logging, level_str.upper(), logging.INFO)

        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
        )
        handler.setLevel(log_level)

        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.setLevel(log_level)

    return logger


def log_metric(name: str, value: Any, unit: str = "") -> None:
    """Log a metric value with formatting.

    Args:
        name: Metric name
        value: Metric value
        unit: Optional unit string (e.g., "ms", "tokens")
    """
    unit_str = f" {unit}" if unit else ""
    console.print(f"[metric]{name}:[/metric] {value}{unit_str}")


def log_tokens(input_tokens: int, output_tokens: int, cached: bool = False) -> None:
    """Log token usage.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cached: Whether the response was cached
    """
    cache_str = " [dim](cached)[/dim]" if cached else ""
    console.print(
        f"[token]Tokens:[/token] {input_tokens} in / {output_tokens} out{cache_str}"
    )


def log_latency(latency_ms: float, operation: str = "Request") -> None:
    """Log latency measurement.

    Args:
        latency_ms: Latency in milliseconds
        operation: Description of the operation
    """
    console.print(f"[latency]{operation}:[/latency] {latency_ms:.2f}ms")


def log_validation_result(stage: str, passed: bool, details: str = "") -> None:
    """Log validation pipeline stage result.

    Args:
        stage: Validation stage name
        passed: Whether validation passed
        details: Optional details about the result
    """
    status = "[success]PASS[/success]" if passed else "[error]FAIL[/error]"
    detail_str = f" - {details}" if details else ""
    console.print(f"Validation [{stage}]: {status}{detail_str}")


def log_generation_start(spec_name: str, template: str) -> None:
    """Log the start of code generation.

    Args:
        spec_name: Name of the workflow specification
        template: Template being used
    """
    console.print(f"\n[info]Generating code for:[/info] {spec_name}")
    console.print(f"[info]Template:[/info] {template}")


def log_generation_complete(loc: int, time_ms: float) -> None:
    """Log successful code generation.

    Args:
        loc: Lines of code generated
        time_ms: Time taken in milliseconds
    """
    console.print(
        f"[success]Generated {loc} lines in {time_ms:.2f}ms[/success]"
    )
