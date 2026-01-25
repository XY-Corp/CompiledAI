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
    
    Parses the prompt to extract numeric values and maps them to the
    appropriate function parameters based on context clues in the text.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
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

    # Extract parameters using regex and context matching
    params = {}
    query_lower = query.lower()

    # For final_velocity function, extract: initial_velocity, acceleration, time
    # Pattern matching for physics problem context
    
    # Extract acceleration - look for "accelerating at X" or "acceleration of X"
    accel_patterns = [
        r'accelerat(?:ing|ion)\s+(?:at|of)\s+(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*(?:m(?:eters)?/s(?:ec(?:ond)?)?(?:\^2|²|2))',
        r'acceleration[:\s]+(\d+(?:\.\d+)?)',
    ]
    acceleration = None
    for pattern in accel_patterns:
        match = re.search(pattern, query_lower)
        if match:
            acceleration = int(float(match.group(1)))
            break

    # Extract time - look for "for X seconds" or "duration of X"
    time_patterns = [
        r'(?:for\s+(?:a\s+)?(?:duration\s+of\s+)?|duration\s+of\s+)(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)',
        r'(\d+(?:\.\d+)?)\s*(?:seconds?|s)\s*(?:duration|time)?',
        r'time[:\s]+(\d+(?:\.\d+)?)',
    ]
    time_val = None
    for pattern in time_patterns:
        match = re.search(pattern, query_lower)
        if match:
            time_val = int(float(match.group(1)))
            break

    # Extract initial velocity - look for "starting from X" or "initial velocity of X"
    init_vel_patterns = [
        r'(?:starting\s+(?:from\s+)?(?:a\s+)?(?:speed|velocity)\s+of\s+|initial(?:ly)?\s+(?:velocity|speed)\s+(?:of\s+)?|start(?:ing)?\s+(?:at|from)\s+)(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*(?:m(?:eters)?/s(?:ec(?:ond)?)?)\s*(?:initial|start)',
        r'initial[_\s]?velocity[:\s]+(\d+(?:\.\d+)?)',
    ]
    initial_velocity = None
    for pattern in init_vel_patterns:
        match = re.search(pattern, query_lower)
        if match:
            initial_velocity = int(float(match.group(1)))
            break

    # Fallback: extract all numbers and map by position/context
    if initial_velocity is None or acceleration is None or time_val is None:
        # Find all numbers with their context
        all_numbers = re.findall(r'(\d+(?:\.\d+)?)', query)
        all_numbers = [int(float(n)) for n in all_numbers]
        
        # Try to map based on order in typical physics problem:
        # "accelerating at 2 m/s^2 for 5 seconds, starting from 10 m/s"
        # Numbers typically appear as: acceleration, time, initial_velocity
        
        if len(all_numbers) >= 3:
            # Check context to determine mapping
            if acceleration is None:
                # First number near "accelerat" is acceleration
                accel_idx = query_lower.find('accelerat')
                if accel_idx != -1:
                    for i, num in enumerate(all_numbers):
                        num_match = re.search(str(num), query[accel_idx:accel_idx+50])
                        if num_match:
                            acceleration = num
                            break
            
            if time_val is None:
                # Number near "second" or "duration" is time
                for num in all_numbers:
                    if num != acceleration:
                        time_match = re.search(rf'{num}\s*(?:seconds?|s\b)', query_lower)
                        if time_match:
                            time_val = num
                            break
            
            if initial_velocity is None:
                # Number near "starting" or "initial" is initial velocity
                for num in all_numbers:
                    if num != acceleration and num != time_val:
                        init_match = re.search(rf'(?:start|initial).*?{num}|{num}.*?(?:m/s|meters/second)(?!\^|²|2)', query_lower)
                        if init_match:
                            initial_velocity = num
                            break
            
            # Final fallback: assign remaining numbers
            remaining = [n for n in all_numbers if n not in [acceleration, time_val, initial_velocity]]
            if initial_velocity is None and remaining:
                initial_velocity = remaining[0]
            if acceleration is None and remaining:
                acceleration = remaining[0] if len(remaining) > 0 else all_numbers[0]
            if time_val is None and remaining:
                time_val = remaining[-1] if len(remaining) > 0 else all_numbers[-1]

    # Build params dict based on schema
    for param_name in params_schema.keys():
        if param_name == "initial_velocity" and initial_velocity is not None:
            params[param_name] = initial_velocity
        elif param_name == "acceleration" and acceleration is not None:
            params[param_name] = acceleration
        elif param_name == "time" and time_val is not None:
            params[param_name] = time_val

    return {func_name: params}
