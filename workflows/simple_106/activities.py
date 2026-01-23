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
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    
    # Extract parameters from query using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Look for specific patterns for this parameter
            if param_name == "max_depth":
                # Pattern: "maximum depth of trees as 5" or "max_depth of 5" or "depth of 5"
                match = re.search(r'(?:maximum\s+)?depth(?:\s+of\s+trees)?\s+(?:as|of|is|=|:)?\s*(\d+)', query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
            elif param_name == "n_estimators":
                # Pattern: "number of estimators as 100" or "n_estimators of 100" or "100 estimators"
                match = re.search(r'(?:number\s+of\s+)?estimators\s+(?:as|of|is|=|:)?\s*(\d+)', query, re.IGNORECASE)
                if not match:
                    match = re.search(r'(\d+)\s+(?:estimators|trees\s+in\s+the\s+forest)', query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
            else:
                # Generic integer extraction - find numbers near the parameter name
                pattern = rf'{param_name}\s*(?:as|of|is|=|:)?\s*(\d+)'
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
        
        elif param_type == "string":
            if param_name == "dataset":
                # Pattern: "on dataset X" or "dataset X" or "on X dataset"
                match = re.search(r'(?:on\s+)?dataset\s+(\S+)', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip(',.')
            else:
                # Generic string extraction
                pattern = rf'{param_name}\s*(?:as|of|is|=|:)?\s*["\']?([^"\']+)["\']?'
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
    
    return {func_name: params}
