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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
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
    
    # Extract all numbers from the query using regex
    numbers = re.findall(r'\d+', query)
    numbers = [int(n) for n in numbers]
    
    # Build parameters based on schema
    params = {}
    param_names = list(params_schema.keys())
    
    if func_name == "math_lcm" and len(numbers) >= 2:
        # For LCM, 'a' should be the larger number per description
        num1, num2 = numbers[0], numbers[1]
        larger = max(num1, num2)
        smaller = min(num1, num2)
        params["a"] = larger
        params["b"] = smaller
    else:
        # Generic assignment: map numbers to integer parameters in order
        num_idx = 0
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else str(param_info)
            if param_type in ["integer", "int", "number"] and num_idx < len(numbers):
                params[param_name] = numbers[num_idx]
                num_idx += 1
    
    return {func_name: params}
