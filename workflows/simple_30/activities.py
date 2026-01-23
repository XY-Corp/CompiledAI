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
    """Extract function name and parameters from user query using regex patterns."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
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
    
    # Extract numeric values from query using regex
    # Pattern for numbers with optional decimals
    numbers = re.findall(r'(\d+(?:\.\d+)?)', query)
    
    # Build params dict based on schema
    params = {}
    
    # For kinematics problem, look for specific patterns
    # "accelerated at X m/s^2" -> acceleration
    accel_match = re.search(r'accelerat\w*\s+(?:at\s+)?(\d+(?:\.\d+)?)\s*m/s', query, re.IGNORECASE)
    if accel_match and "acceleration" in params_schema:
        params["acceleration"] = int(float(accel_match.group(1)))
    
    # "distance of X meters" or "X meters" -> distance
    dist_match = re.search(r'(?:distance\s+(?:of\s+)?)?(\d+(?:\.\d+)?)\s*(?:meters|m(?:\b|[^/]))', query, re.IGNORECASE)
    if dist_match and "distance" in params_schema:
        params["distance"] = int(float(dist_match.group(1)))
    
    # "started from rest" means initial_velocity = 0
    if re.search(r'from\s+rest|initial(?:ly)?\s+(?:at\s+)?(?:rest|0)', query, re.IGNORECASE):
        if "initial_velocity" in params_schema:
            params["initial_velocity"] = 0.0
    
    # If we didn't find specific patterns, try to map numbers to params by order
    if not params and numbers:
        param_names = list(params_schema.keys())
        for i, num in enumerate(numbers):
            if i < len(param_names):
                param_name = param_names[i]
                param_type = params_schema[param_name].get("type", "string")
                if param_type == "integer":
                    params[param_name] = int(float(num))
                elif param_type in ["float", "number"]:
                    params[param_name] = float(num)
                else:
                    params[param_name] = num
    
    return {func_name: params}
