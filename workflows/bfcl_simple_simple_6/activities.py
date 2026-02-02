import re
import json
from typing import Any


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
    """Extract function call parameters from user query using regex.
    
    Returns format: {"function_name": {"param1": val1, ...}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL-style nested structure
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = data.get("content", str(prompt))
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions list
    funcs = []
    if functions:
        if isinstance(functions, str):
            try:
                funcs = json.loads(functions)
            except json.JSONDecodeError:
                funcs = []
        else:
            funcs = functions
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        # Try multiple patterns to extract named parameter values
        # Pattern 1: "param_name=value" or "param_name = value"
        pattern1 = rf'{param_name}\s*=\s*(-?\d+(?:\.\d+)?)'
        match = re.search(pattern1, query, re.IGNORECASE)
        
        if match:
            value = match.group(1)
            if param_type == "integer":
                params[param_name] = int(value)
            elif param_type in ["float", "number"]:
                params[param_name] = float(value)
            else:
                params[param_name] = value
            continue
        
        # Pattern 2: "param_name is value" or "param_name: value"
        pattern2 = rf'{param_name}\s*(?:is|:)\s*(-?\d+(?:\.\d+)?)'
        match = re.search(pattern2, query, re.IGNORECASE)
        
        if match:
            value = match.group(1)
            if param_type == "integer":
                params[param_name] = int(value)
            elif param_type in ["float", "number"]:
                params[param_name] = float(value)
            else:
                params[param_name] = value
            continue
    
    # If we didn't find all params with named patterns, try positional extraction
    if len(params) < len(params_schema):
        # Extract all numbers from the query
        all_numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
        
        # Map remaining params by position
        num_idx = 0
        for param_name, param_info in params_schema.items():
            if param_name in params:
                continue  # Already extracted
            
            param_type = param_info.get("type", "string")
            
            if param_type in ["integer", "float", "number"] and num_idx < len(all_numbers):
                value = all_numbers[num_idx]
                if param_type == "integer":
                    params[param_name] = int(float(value))
                else:
                    params[param_name] = float(value)
                num_idx += 1
    
    return {func_name: params}
