"""Template resolution utilities for variable interpolation in DSL.

This module handles the ${{ variable }} syntax used in DSL parameters.
"""

from __future__ import annotations

import re
from typing import Any, Dict


# ============================================================================
# Template Resolution for Variable Interpolation
# ============================================================================

VAR_PATTERN = re.compile(r"\$\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}")


def validate_name_field(value: str, field_name: str, location: str) -> str:
    """
    Validate that a name field does not use template syntax.

    Name fields (items, result, item_variable) expect raw variable names
    with optional dot notation for nested access. Template syntax ${{ }}
    is only for params values.

    Args:
        value: The field value to validate
        field_name: Name of the field (for error messages)
        location: Location in DSL tree (for error messages)

    Returns:
        The validated value (unchanged)

    Raises:
        ValueError: If template syntax is detected

    Examples:
        Valid:   "order_tokens", "order.line_items"
        Invalid: "${{ order_tokens }}", "${{ order.line_items }}"
    """
    match = VAR_PATTERN.search(value)
    if match:
        inner_var = match.group(1)
        raise ValueError(
            f"Invalid syntax in '{field_name}' at {location}: '{value}'\n\n"
            f"Name fields expect raw variable names, not template syntax.\n"
            f"  Use: {field_name}: {inner_var}\n"
            f"  Not: {field_name}: ${{{{ {inner_var} }}}}\n\n"
            f"Template syntax ${{{{ }}}} is only for 'params' values where you need to\n"
            f"distinguish between literal strings and variable references.\n"
            f"Name fields (items, result, item_variable) always reference variables,\n"
            f"so no template syntax is needed. Dot notation is supported for nested access."
        )
    return value


def _resolve_path(var_path: str, context: Dict[str, Any]) -> Any:
    """Resolve a dotted variable path against the provided context."""

    if "." not in var_path:
        if var_path not in context:
            raise KeyError(
                f"Variable '{var_path}' not found in workflow context. "
                f"Available variables: {list(context.keys())}"
            )
        return context[var_path]

    parts = var_path.split(".")
    current: Any = context
    for part in parts:
        if not isinstance(current, dict):
            raise ValueError(
                f"Cannot access '{part}' in '{var_path}' - {type(current).__name__} is not a dict"
            )
        if part not in current:
            raise ValueError(
                f"Key '{part}' not found in '{var_path}'. "
                f"Available keys: {list(current.keys())}"
            )
        current = current[part]

    return current


def resolve_template_scalar(value: Any, context: Dict[str, Any]) -> Any:
    """
    Resolve a single scalar: either a variable reference or a literal.

    Examples:
        "${{ user_id }}" -> looks up context["user_id"]
        "${{ invoice_item.claim_token }}" -> looks up context["invoice_item"]["claim_token"]
        "items"          -> returns "items" (literal)
        123              -> returns 123 (literal)
    """
    if not isinstance(value, str):
        return value

    match = VAR_PATTERN.fullmatch(value)
    if match:
        return _resolve_path(match.group(1), context)

    # Support mixed literal + template strings by substituting occurrences.
    def _replacement(m):
        resolved = _resolve_path(m.group(1), context)
        return str(resolved)

    if VAR_PATTERN.search(value):
        return VAR_PATTERN.sub(_replacement, value)

    return value  # literal string


def resolve_templates(value: Any, context: Dict[str, Any]) -> Any:
    """
    Recursively resolve templates in dicts/lists/scalars.

    Keeps it flexible if we later allow nested objects in params.
    """
    if isinstance(value, dict):
        return {k: resolve_templates(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_templates(v, context) for v in value]
    return resolve_template_scalar(value, context)
