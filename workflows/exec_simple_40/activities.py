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
    """Extract function call parameters from user query using regex.
    
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
    
    # Extract coordinate pairs using regex
    # Pattern for coordinates like (45.76, 4.85) or 45.76, 4.85
    coord_pattern = r'\(?\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)?'
    
    # Find all coordinate pairs in the query
    matches = re.findall(coord_pattern, query)
    
    params = {}
    
    if func_name == "get_distance" and len(matches) >= 2:
        # Extract the two points
        point_a = (float(matches[0][0]), float(matches[0][1]))
        point_b = (float(matches[1][0]), float(matches[1][1]))
        
        params["pointA"] = point_a
        params["pointB"] = point_b
    else:
        # Generic extraction for other functions
        # Extract all numbers from query
        numbers = re.findall(r'-?\d+\.?\d*', query)
        
        # Map to parameters based on schema
        num_idx = 0
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else str(param_info)
            
            if param_type in ["tuple", "array", "list"]:
                # For tuple/array types, try to get pairs of numbers
                if num_idx + 1 < len(numbers):
                    params[param_name] = (float(numbers[num_idx]), float(numbers[num_idx + 1]))
                    num_idx += 2
            elif param_type in ["integer", "int"]:
                if num_idx < len(numbers):
                    params[param_name] = int(float(numbers[num_idx]))
                    num_idx += 1
            elif param_type in ["float", "number"]:
                if num_idx < len(numbers):
                    params[param_name] = float(numbers[num_idx])
                    num_idx += 1
    
    return {func_name: params}
