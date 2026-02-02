import re
import json
from typing import Any, Dict, List, Optional


async def extract_function_call(
    prompt: str,
    functions: list = None,
    user_query: str = None,
    tools: list = None,
    tool_name_mapping: dict = None,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex to extract values - NO LLM calls needed for explicit values in text.
    """
    # Step 1: Parse prompt structure (may be JSON string or nested BFCL format)
    query = prompt
    if isinstance(prompt, str):
        try:
            data = json.loads(prompt)
            # Handle BFCL nested format: {"question": [[{"content": "..."}]]}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                        query = data["question"][0][0].get("content", prompt)
        except (json.JSONDecodeError, TypeError, KeyError):
            query = prompt
    
    # Step 2: Parse functions list (may be JSON string)
    funcs = functions
    if isinstance(functions, str):
        try:
            funcs = json.loads(functions)
        except (json.JSONDecodeError, TypeError):
            funcs = []
    
    if not funcs:
        funcs = []
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Step 3: Extract parameter values using REGEX (no LLM needed!)
    extracted_params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Map extracted values to parameter names based on schema
    num_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "int"]:
            if num_idx < len(numbers):
                extracted_params[param_name] = int(numbers[num_idx])
                num_idx += 1
        elif param_type in ["float", "number"]:
            if num_idx < len(numbers):
                extracted_params[param_name] = float(numbers[num_idx])
                num_idx += 1
        elif param_type == "string":
            # Try to extract string values using common patterns
            # Pattern: "for X" or "in X" or "of X" or quoted strings
            string_patterns = [
                r'"([^"]+)"',  # Quoted strings
                r"'([^']+)'",  # Single quoted strings
                r'(?:for|in|of|with|named?)\s+([A-Za-z][A-Za-z0-9_\s]+?)(?:\s+(?:and|with|using|,)|[.]|$)',
            ]
            for pattern in string_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    extracted_params[param_name] = match.group(1).strip()
                    break
    
    # Return in exact format: {func_name: {params}}
    return {func_name: extracted_params}
