import re
import json
from typing import Any


async def extract_function_call(
    prompt: str,
    functions: list,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from natural language prompt.
    
    Parses the prompt to extract the function name and parameters,
    returning them in the format {"function_name": {"param1": val1, ...}}.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract integers based on context clues in the query
            if param_name == "max_depth" or "depth" in param_name.lower():
                # Look for "depth of/as X" pattern
                match = re.search(r'(?:depth\s+(?:of|as|is|=|:)?\s*)(\d+)', query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
            elif param_name == "n_estimators" or "estimator" in param_name.lower():
                # Look for "estimators as/of X" or "number of estimators as X"
                match = re.search(r'(?:estimators?\s+(?:of|as|is|=|:)?\s*)(\d+)', query, re.IGNORECASE)
                if not match:
                    match = re.search(r'(\d+)\s*(?:estimators?|trees)', query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
            else:
                # Generic number extraction - find all numbers and try to match by position/context
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    # Try to find number near the parameter name or description keywords
                    for num in numbers:
                        if num not in [str(v) for v in params.values()]:
                            params[param_name] = int(num)
                            break
        
        elif param_type == "string":
            if param_name == "dataset" or "dataset" in param_desc:
                # Look for "dataset X" or "on dataset X" or "on X"
                match = re.search(r'(?:on\s+(?:dataset\s+)?|dataset\s+)([a-zA-Z_][a-zA-Z0-9_]*)', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1)
            else:
                # Generic string extraction - look for quoted strings or identifiers
                match = re.search(r'"([^"]+)"', query)
                if match:
                    params[param_name] = match.group(1)
    
    return {func_name: params}
