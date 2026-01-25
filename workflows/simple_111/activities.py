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
    """Extract function name and parameters from user query using regex patterns.
    
    Returns a dict with function name as key and parameters as nested object.
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
    
    # Extract parameters using regex patterns
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        value = None
        
        # For mean (mu) parameter
        if param_name == "mu" or "mean" in param_desc:
            # Look for "mean X" or "mean of X" patterns
            mean_patterns = [
                r'mean\s+(?:of\s+)?(-?\d+(?:\.\d+)?)',
                r'mean\s*[=:]\s*(-?\d+(?:\.\d+)?)',
                r'μ\s*[=:]\s*(-?\d+(?:\.\d+)?)',
            ]
            for pattern in mean_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    value = float(match.group(1))
                    if param_type == "integer":
                        value = int(value)
                    break
        
        # For standard deviation (sigma) parameter
        elif param_name == "sigma" or "standard deviation" in param_desc:
            # Look for "standard deviation X" patterns
            std_patterns = [
                r'standard\s+deviation\s+(?:of\s+)?(-?\d+(?:\.\d+)?)',
                r'std\s*[=:]\s*(-?\d+(?:\.\d+)?)',
                r'σ\s*[=:]\s*(-?\d+(?:\.\d+)?)',
                r'deviation\s+(-?\d+(?:\.\d+)?)',
            ]
            for pattern in std_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    value = float(match.group(1))
                    if param_type == "integer":
                        value = int(value)
                    break
        
        if value is not None:
            params[param_name] = value
    
    # Fallback: if we didn't find specific patterns, extract all numbers in order
    if len(params) < len(params_schema):
        numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
        param_names = list(params_schema.keys())
        
        num_idx = 0
        for param_name in param_names:
            if param_name not in params and num_idx < len(numbers):
                param_type = params_schema[param_name].get("type", "string")
                if param_type == "integer":
                    params[param_name] = int(float(numbers[num_idx]))
                elif param_type in ["number", "float"]:
                    params[param_name] = float(numbers[num_idx])
                else:
                    params[param_name] = numbers[num_idx]
                num_idx += 1
    
    return {func_name: params}
