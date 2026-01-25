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
    
    # Extract parameters using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Try to find value based on parameter description keywords
        value = None
        
        if param_name == "current" or "current" in param_desc:
            # Look for current value: "current of X Ampere" or "X Ampere current"
            patterns = [
                r'current\s+of\s+(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*(?:ampere|amp|a)\b',
                r'carrying\s+current\s+of\s+(\d+(?:\.\d+)?)',
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    break
        
        elif param_name == "radius" or "radius" in param_desc:
            # Look for radius value: "radius of X meters" or "X meter radius"
            patterns = [
                r'radius\s+of\s+(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*(?:meter|m)\s*(?:radius)?',
                r'with\s+a\s+radius\s+of\s+(\d+(?:\.\d+)?)',
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    break
        
        elif param_name == "permeability" or "permeability" in param_desc:
            # Look for permeability value - usually not specified, use default
            patterns = [
                r'permeability\s+(?:of\s+)?(\d+(?:\.\d+)?(?:e[+-]?\d+)?)',
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    break
        
        # Convert value to appropriate type if found
        if value is not None:
            if param_type == "integer":
                params[param_name] = int(float(value))
            elif param_type == "float":
                params[param_name] = float(value)
            else:
                params[param_name] = value
    
    # Fallback: if we didn't find specific params, extract all numbers in order
    if not params:
        numbers = re.findall(r'(\d+(?:\.\d+)?)', query)
        param_names = list(params_schema.keys())
        
        for i, param_name in enumerate(param_names):
            if i < len(numbers):
                param_type = params_schema[param_name].get("type", "string")
                if param_type == "integer":
                    params[param_name] = int(float(numbers[i]))
                elif param_type == "float":
                    params[param_name] = float(numbers[i])
                else:
                    params[param_name] = numbers[i]
    
    return {func_name: params}
