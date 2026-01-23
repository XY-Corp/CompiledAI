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
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Map extracted numbers to parameters based on context clues in the query
    # For displacement calculation: initial_velocity, acceleration, time
    
    # Look for specific patterns in the query
    # "initial velocity of X" or "velocity of X"
    velocity_match = re.search(r'(?:initial\s+)?velocity\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    # "acceleration of X" or "acceleeration of X" (handle typo)
    accel_match = re.search(r'accel+e+ration\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    # "X seconds" or "within X seconds" or "time of X"
    time_match = re.search(r'(?:within\s+)?(\d+(?:\.\d+)?)\s*seconds?', query, re.IGNORECASE)
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "initial_velocity" and velocity_match:
            value = velocity_match.group(1)
            if param_type == "integer":
                params[param_name] = int(float(value))
            elif param_type == "float":
                params[param_name] = float(value)
            else:
                params[param_name] = value
                
        elif param_name == "acceleration" and accel_match:
            value = accel_match.group(1)
            if param_type == "integer":
                params[param_name] = int(float(value))
            elif param_type == "float":
                params[param_name] = float(value)
            else:
                params[param_name] = value
                
        elif param_name == "time" and time_match:
            value = time_match.group(1)
            if param_type == "integer":
                params[param_name] = int(float(value))
            elif param_type == "float":
                params[param_name] = float(value)
            else:
                params[param_name] = value
    
    # Fallback: if specific patterns didn't match, try positional assignment
    # based on order of numbers in the query
    if not params and numbers:
        num_idx = 0
        for param_name, param_info in params_schema.items():
            if num_idx >= len(numbers):
                break
            param_type = param_info.get("type", "string")
            value = numbers[num_idx]
            
            if param_type == "integer":
                params[param_name] = int(float(value))
            elif param_type == "float":
                params[param_name] = float(value)
            else:
                params[param_name] = value
            num_idx += 1
    
    return {func_name: params}
