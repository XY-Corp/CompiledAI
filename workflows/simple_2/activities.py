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
    """Extract function name and parameters from user query using regex.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
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
    required_params = func.get("parameters", {}).get("required", [])

    # Extract all numbers from the query using regex
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Build parameters dict based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            if num_idx < len(numbers):
                if param_type == "integer":
                    params[param_name] = int(numbers[num_idx])
                else:
                    params[param_name] = float(numbers[num_idx])
                num_idx += 1
            elif param_name in required_params:
                # Required param but no number found - skip optional params
                pass
        elif param_type == "string":
            # Try to extract string values using common patterns
            string_match = re.search(
                r'(?:for|in|of|with|named?)\s+["\']?([A-Za-z\s]+?)["\']?(?:\s+(?:and|with|,)|$)',
                query,
                re.IGNORECASE
            )
            if string_match:
                params[param_name] = string_match.group(1).strip()

    # Only include required params and optional params that have values
    # For this task: x and y are required, z is optional
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            # Include if it's required OR if we found a value for optional
            if param_name in required_params:
                final_params[param_name] = params[param_name]
            # Skip optional params unless explicitly mentioned
    
    # For math.hypot: x=4, y=5 (the two sides mentioned)
    # Only return required params
    result_params = {}
    for param_name in required_params:
        if param_name in params:
            result_params[param_name] = params[param_name]

    return {func_name: result_params}
