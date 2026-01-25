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
    """Extract function name and parameters from user query using regex patterns.
    
    Returns a dict with function name as key and parameters as nested object.
    """
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

    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])

    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    number_idx = 0

    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "number", "float"]:
            # Assign numbers to numeric parameters in order
            if number_idx < len(numbers):
                value = numbers[number_idx]
                if param_type == "integer":
                    params[param_name] = int(float(value))
                else:
                    params[param_name] = float(value)
                number_idx += 1
        elif param_type == "string":
            # Check if this is a unit parameter
            if "unit" in param_name.lower() or "unit" in param_desc:
                # Look for unit mentions in query
                unit_patterns = [
                    r'\b(meters?|m)\b',
                    r'\b(centimeters?|cm)\b',
                    r'\b(kilometers?|km)\b',
                    r'\b(feet|ft)\b',
                    r'\b(inches?|in)\b',
                    r'\b(miles?|mi)\b',
                    r'\b(units?)\b',
                ]
                for pattern in unit_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).lower()
                        break
                # Only include if found (it's optional)
            else:
                # Generic string extraction - look for quoted strings or named entities
                quoted = re.search(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted.group(1)

    # Ensure all required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to find a value
            if params_schema.get(req_param, {}).get("type") in ["integer", "number", "float"]:
                if number_idx < len(numbers):
                    value = numbers[number_idx]
                    if params_schema[req_param].get("type") == "integer":
                        params[req_param] = int(float(value))
                    else:
                        params[req_param] = float(value)
                    number_idx += 1

    return {func_name: params}
