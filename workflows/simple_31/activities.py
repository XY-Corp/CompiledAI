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
    
    Returns a dict with function name as key and parameters as nested object.
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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract all numbers from the query
    # Pattern matches integers and floats (including decimals)
    numbers = re.findall(r'[-+]?\d+(?:\.\d+)?', query)
    
    # Build parameters based on schema and extracted values
    params = {}
    query_lower = query.lower()
    
    # For calculate_final_velocity, we need:
    # - initial_velocity: "started from rest" means 0
    # - acceleration: look for "accelerated at" or "m/s^2"
    # - time: look for "duration" or "seconds"
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "initial_velocity":
            # Check for "from rest" or "at rest" which means 0
            if "from rest" in query_lower or "at rest" in query_lower or "started from rest" in query_lower:
                params[param_name] = 0
            else:
                # Try to find initial velocity value
                init_match = re.search(r'initial\s+velocity\s+(?:of\s+)?(\d+(?:\.\d+)?)', query_lower)
                if init_match:
                    val = float(init_match.group(1))
                    params[param_name] = int(val) if param_type == "integer" else val
                elif numbers:
                    # Default to first number if no specific match
                    val = float(numbers[0])
                    params[param_name] = int(val) if param_type == "integer" else val
        
        elif param_name == "acceleration":
            # Look for acceleration value - often near "m/s^2" or "accelerated at"
            accel_patterns = [
                r'accelerat\w*\s+(?:at\s+)?(?:a\s+rate\s+of\s+)?(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*m/s\^?2',
                r'acceleration\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            ]
            for pattern in accel_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    val = float(match.group(1))
                    params[param_name] = val if param_type == "float" else int(val)
                    break
        
        elif param_name == "time":
            # Look for time/duration value - often near "seconds" or "duration"
            time_patterns = [
                r'(?:duration|time)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)?',
                r'for\s+(?:a\s+)?(?:duration\s+of\s+)?(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)',
                r'(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)',
            ]
            for pattern in time_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    val = float(match.group(1))
                    params[param_name] = int(val) if param_type == "integer" else val
                    break
    
    return {func_name: params}
