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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
                else:
                    query = str(prompt)
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
    
    # Extract parameters based on schema
    params = {}
    
    # Extract arrays from the query - look for patterns like [1, 2, 3]
    array_pattern = r'\[([^\]]+)\]'
    arrays_found = re.findall(array_pattern, query)
    
    # Parse arrays into lists of integers
    parsed_arrays = []
    for arr_str in arrays_found:
        try:
            # Parse comma-separated values
            values = [int(x.strip()) for x in arr_str.split(',') if x.strip()]
            if values:
                parsed_arrays.append(values)
        except ValueError:
            continue
    
    # Check for equal_variance mention
    equal_variance = True  # default
    query_lower = query.lower()
    if "unequal variance" in query_lower or "not equal variance" in query_lower or "assuming unequal" in query_lower:
        equal_variance = False
    elif "equal variance" in query_lower or "assuming equal" in query_lower:
        equal_variance = True
    
    # Map extracted values to parameter names
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            # Assign arrays in order: group1 gets first, group2 gets second
            if param_name == "group1" and len(parsed_arrays) >= 1:
                params[param_name] = parsed_arrays[0]
            elif param_name == "group2" and len(parsed_arrays) >= 2:
                params[param_name] = parsed_arrays[1]
        elif param_type == "boolean":
            if param_name == "equal_variance":
                params[param_name] = equal_variance
    
    return {func_name: params}
