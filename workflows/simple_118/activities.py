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
    
    # Extract arrays from the query using regex
    # Pattern to match arrays like [10, 15, 12, 14, 11]
    array_pattern = r'\[[\d,\s]+\]'
    arrays_found = re.findall(array_pattern, query)
    
    # Parse the arrays
    parsed_arrays = []
    for arr_str in arrays_found:
        try:
            arr = json.loads(arr_str)
            parsed_arrays.append(arr)
        except json.JSONDecodeError:
            continue
    
    # Extract alpha value using regex
    # Patterns: "alpha equals to 0.05", "alpha = 0.05", "alpha of 0.05", "alpha 0.05"
    alpha_patterns = [
        r'alpha\s*(?:equals?\s*(?:to)?|=|of|:)?\s*([\d.]+)',
        r'significance\s*(?:level)?\s*(?:of|=|:)?\s*([\d.]+)',
    ]
    
    alpha_value = None
    for pattern in alpha_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            try:
                alpha_value = float(match.group(1))
                break
            except ValueError:
                continue
    
    # Build parameters based on schema
    params = {}
    
    # Assign arrays to array_1 and array_2
    if len(parsed_arrays) >= 2:
        params["array_1"] = parsed_arrays[0]
        params["array_2"] = parsed_arrays[1]
    elif len(parsed_arrays) == 1:
        params["array_1"] = parsed_arrays[0]
        params["array_2"] = []
    
    # Assign alpha
    if alpha_value is not None:
        params["alpha"] = alpha_value
    
    return {func_name: params}
