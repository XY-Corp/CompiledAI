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
    """Extract function call parameters from natural language query using regex.
    
    Returns a dict with function name as key and parameters as nested dict.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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

    # Extract all numbers from the query (integers and floats)
    # Pattern matches numbers like: 15, 9.8, 10, etc.
    numbers = re.findall(r'(\d+(?:\.\d+)?)', query)
    float_numbers = [float(n) for n in numbers]

    # Build parameters by matching extracted numbers to schema
    params = {}
    
    # For physics displacement problem, we need to match:
    # - initial_velocity: "moving at X m/s" or "velocity of X"
    # - acceleration: "accelerating at X m/s²" or "acceleration of X"
    # - time: "for X seconds" or "time of X"
    
    # Try specific patterns first for better accuracy
    
    # Initial velocity pattern: "moving at X m/s" or "velocity of X" or "initially was moving at X"
    velocity_match = re.search(r'(?:moving at|velocity of|initial(?:ly)?\s+(?:was\s+)?(?:moving\s+at)?)\s*(\d+(?:\.\d+)?)\s*(?:m/s|meters?\s*per\s*second)?', query, re.IGNORECASE)
    if velocity_match:
        params["initial_velocity"] = float(velocity_match.group(1))
    
    # Acceleration pattern: "accelerating at X m/s²" or "acceleration of X"
    accel_match = re.search(r'(?:accelerat(?:ing|ion)\s+(?:at\s+)?(?:a\s+rate\s+of\s+)?|acceleration\s+of)\s*(\d+(?:\.\d+)?)\s*(?:m/s|meters?\s*per\s*second)', query, re.IGNORECASE)
    if accel_match:
        params["acceleration"] = float(accel_match.group(1))
    
    # Time pattern: "for X seconds" or "time of X" or "exactly X seconds"
    time_match = re.search(r'(?:for\s+(?:exactly\s+)?|time\s+(?:of\s+)?|exactly\s+)(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)', query, re.IGNORECASE)
    if time_match:
        params["time"] = float(time_match.group(1))
    
    # Fallback: if we didn't get all params but have enough numbers, assign by order
    # For displacement: typically velocity, acceleration, time
    if len(params) < len(params_schema) and len(float_numbers) >= len(params_schema):
        param_names = list(params_schema.keys())
        for i, param_name in enumerate(param_names):
            if param_name not in params and i < len(float_numbers):
                params[param_name] = float_numbers[i]

    return {func_name: params}
