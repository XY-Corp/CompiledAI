"""BFCL-specific helpers for building tool schemas for LLM tool calling.

This keeps BFCL schema quirks in the datasets layer so baselines can remain
dataset-agnostic and just consume generic `tools` from context.
"""

from __future__ import annotations

import re
from typing import Any


def sanitize_tool_name(name: str) -> str:
    """Sanitize function name to match Anthropic's pattern: ^[a-zA-Z0-9_-]{1,128}$."""
    # Replace dots and other invalid chars with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    # Truncate to 128 chars
    return sanitized[:128]


def fix_json_schema(schema: dict) -> dict:
    """Fix common JSON Schema issues in BFCL function definitions.

    BFCL uses non-standard types that Anthropic's API rejects:
    - "dict" -> "object"
    - "float" -> "number"
    - "list" -> "array"
    - "int" -> "integer"
    """
    if not isinstance(schema, dict):
        return schema

    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "type":
            type_mapping = {
                "dict": "object",
                "float": "number",
                "list": "array",
                "int": "integer",
            }
            result[key] = type_mapping.get(value, value)
        elif isinstance(value, dict):
            result[key] = fix_json_schema(value)
        elif isinstance(value, list):
            result[key] = [
                fix_json_schema(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def build_tools_from_functions(functions: list[dict]) -> tuple[list[dict], dict[str, str]]:
    """Convert BFCL function definitions to generic tool format.

    Returns:
        tools: List of tool specs compatible with LLM tool calling.
        name_mapping: Mapping from sanitized tool name -> original function name.
    """
    tools: list[dict] = []
    name_mapping: dict[str, str] = {}

    for func in functions:
        original_name = func.get("name", "")
        if not original_name:
            continue

        sanitized_name = sanitize_tool_name(original_name)
        name_mapping[sanitized_name] = original_name

        params = func.get("parameters", {})
        params = fix_json_schema(params)

        tool = {
            "type": "function",
            "function": {
                "name": sanitized_name,
                "description": func.get("description", ""),
                "parameters": params,
            },
        }
        tools.append(tool)

    return tools, name_mapping

