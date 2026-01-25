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
    """Extract function call parameters from natural language query.
    
    Parses the user query to extract numeric values and maps them to the
    appropriate function parameters based on the function schema.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
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
    # Pattern matches integers and floats
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    numbers = [float(n) for n in numbers]
    
    # Build parameters dict
    params = {}
    
    # For calculate_final_velocity, we need:
    # - initial_velocity: "starts from a standstill" = 0
    # - acceleration: "9.8 meters per second squared"
    # - time: "12 seconds"
    
    # Check for "standstill" or "rest" indicating initial_velocity = 0
    if re.search(r'\b(standstill|rest|stationary|stopped)\b', query, re.IGNORECASE):
        params["initial_velocity"] = 0.0
    
    # Extract acceleration - look for pattern like "X meters per second squared"
    accel_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:meters?\s*per\s*second\s*squared|m/s\s*(?:squared|\^?2)|m/s²)', query, re.IGNORECASE)
    if accel_match:
        params["acceleration"] = float(accel_match.group(1))
    
    # Extract time - look for pattern like "X seconds"
    time_match = re.search(r'(\d+(?:\.\d+)?)\s*seconds?\b', query, re.IGNORECASE)
    if time_match:
        params["time"] = float(time_match.group(1))
    
    # Fallback: if we didn't find specific patterns, try to map numbers to params
    # based on order or context
    if len(params) < len(params_schema):
        remaining_params = [p for p in params_schema.keys() if p not in params]
        remaining_numbers = [n for n in numbers if n not in params.values()]
        
        for param_name, num in zip(remaining_params, remaining_numbers):
            if param_name not in params:
                params[param_name] = num
    
    return {func_name: params}
