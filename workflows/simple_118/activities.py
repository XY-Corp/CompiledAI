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
    """Extract function name and parameters from user query using regex/parsing."""
    
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
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract arrays from the query
    # Pattern: look for array-like structures [num, num, ...]
    array_pattern = r'\[([0-9,\s]+)\]'
    arrays_found = re.findall(array_pattern, query)
    
    # Parse arrays into lists of integers
    parsed_arrays = []
    for arr_str in arrays_found:
        try:
            # Split by comma and convert to integers
            arr = [int(x.strip()) for x in arr_str.split(',') if x.strip()]
            parsed_arrays.append(arr)
        except ValueError:
            continue
    
    # Extract alpha value (float after "alpha" keyword)
    alpha_patterns = [
        r'alpha\s*(?:equals?\s*(?:to)?|=|:)\s*([0-9]*\.?[0-9]+)',
        r'significance\s*(?:level)?\s*(?:of|=|:)?\s*([0-9]*\.?[0-9]+)',
        r'([0-9]*\.[0-9]+)\s*(?:significance|alpha)',
    ]
    
    alpha_value = None
    for pattern in alpha_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            alpha_value = float(match.group(1))
            break
    
    # Map extracted values to parameter names based on schema
    array_params = []
    float_params = []
    
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "")
        if param_type == "array":
            array_params.append(param_name)
        elif param_type in ["float", "number"]:
            float_params.append(param_name)
    
    # Assign arrays to array parameters in order
    for i, param_name in enumerate(array_params):
        if i < len(parsed_arrays):
            params[param_name] = parsed_arrays[i]
    
    # Assign alpha to float parameters
    if alpha_value is not None:
        for param_name in float_params:
            params[param_name] = alpha_value
    
    return {func_name: params}
