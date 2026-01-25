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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
    # Parse prompt - may be JSON string or dict
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from nested structure
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - may be JSON string or list
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # For quadratic equation: look for a=X, b=Y, c=Z patterns
    # Pattern 1: "a=2, b=5, c=3" or "a=2 b=5 c=3"
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        # Try explicit assignment pattern: "param_name=value" or "param_name = value"
        pattern = rf'\b{param_name}\s*=\s*(-?\d+(?:\.\d+)?)'
        match = re.search(pattern, query, re.IGNORECASE)
        
        if match:
            value = match.group(1)
            if param_type == "integer":
                params[param_name] = int(float(value))
            elif param_type in ["number", "float"]:
                params[param_name] = float(value)
            else:
                params[param_name] = value
    
    # If we didn't find all params with explicit assignment, try positional extraction
    if len(params) < len(params_schema):
        # Extract all numbers from the query
        all_numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
        
        # Map remaining params to numbers in order
        num_idx = 0
        for param_name, param_info in params_schema.items():
            if param_name not in params and num_idx < len(all_numbers):
                param_type = param_info.get("type", "string")
                value = all_numbers[num_idx]
                
                if param_type == "integer":
                    params[param_name] = int(float(value))
                elif param_type in ["number", "float"]:
                    params[param_name] = float(value)
                else:
                    params[param_name] = value
                
                num_idx += 1
    
    return {func_name: params}
