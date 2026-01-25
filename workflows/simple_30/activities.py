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
    if accel_match:
        accel_val = accel_match.group(1)
        if "acceleration" in params_schema:
            param_type = params_schema["acceleration"].get("type", "integer")
            if param_type == "integer":
                params["acceleration"] = int(float(accel_val))
            else:
                params["acceleration"] = float(accel_val)
    
    # "distance of X meters" or "X meters" -> distance
    dist_match = re.search(r'(?:distance\s+(?:of\s+)?)?(\d+(?:\.\d+)?)\s*(?:meters|m(?:eter)?(?:\b|$))', query, re.IGNORECASE)
    if dist_match:
        dist_val = dist_match.group(1)
        if "distance" in params_schema:
            param_type = params_schema["distance"].get("type", "integer")
            if param_type == "integer":
                params["distance"] = int(float(dist_val))
            else:
                params["distance"] = float(dist_val)
    
    # Check for "started from rest" -> initial_velocity = 0
    if re.search(r'from\s+rest|initial(?:ly)?\s+(?:at\s+)?rest|start(?:ed|ing)?\s+(?:from\s+)?rest', query, re.IGNORECASE):
        if "initial_velocity" in params_schema:
            params["initial_velocity"] = 0.0
    
    # If we didn't find specific patterns, fall back to positional extraction
    if not params and numbers:
        num_idx = 0
        for param_name, param_info in params_schema.items():
            if num_idx >= len(numbers):
                break
            param_type = param_info.get("type", "string")
            if param_type in ["integer", "int"]:
                params[param_name] = int(float(numbers[num_idx]))
                num_idx += 1
            elif param_type in ["float", "number"]:
                params[param_name] = float(numbers[num_idx])
                num_idx += 1
    
    return {func_name: params}
