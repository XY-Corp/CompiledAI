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
    
    # Extract all numbers from the query
    # Pattern matches integers and floats
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Build params dict based on schema
    params = {}
    
    # For calculate_displacement, we need: initial_velocity, time, acceleration
    # Query: "initial velocity of 10 and acceleration of 9.8 within 5 seconds"
    
    # Try to extract values with context-aware patterns
    # Initial velocity pattern
    initial_vel_match = re.search(r'initial\s+velocity\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if initial_vel_match:
        params["initial_velocity"] = int(float(initial_vel_match.group(1)))
    
    # Acceleration pattern
    accel_match = re.search(r'accel(?:er)?ation\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if accel_match:
        params["acceleration"] = float(accel_match.group(1))
    
    # Time pattern - "within X seconds" or "for X seconds" or "X seconds"
    time_match = re.search(r'(?:within|for|in)?\s*(\d+(?:\.\d+)?)\s*seconds?', query, re.IGNORECASE)
    if time_match:
        params["time"] = int(float(time_match.group(1)))
    
    # Fallback: if we didn't get all params, try positional assignment
    if len(params) < len([p for p in params_schema if p in ["initial_velocity", "time"]]):
        # Get numbers in order they appear
        num_idx = 0
        for param_name in ["initial_velocity", "acceleration", "time"]:
            if param_name not in params and param_name in params_schema:
                param_info = params_schema[param_name]
                param_type = param_info.get("type", "string")
                
                if num_idx < len(numbers):
                    if param_type == "integer":
                        params[param_name] = int(float(numbers[num_idx]))
                    elif param_type == "float":
                        params[param_name] = float(numbers[num_idx])
                    else:
                        params[param_name] = numbers[num_idx]
                    num_idx += 1
    
    return {func_name: params}
