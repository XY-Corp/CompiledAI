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
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    func_name = func.get("name", "unknown")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract numbers from query using regex
    # Match integers and floats
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    numbers = [int(n) if '.' not in n else float(n) for n in numbers]
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "number", "float"]:
            if num_idx < len(numbers):
                # Check if description mentions "larger" or "first" for ordering
                if "larger" in param_desc or "first" in param_desc:
                    # Assign the larger number
                    if len(numbers) >= 2:
                        params[param_name] = max(numbers[0], numbers[1]) if param_type == "integer" else float(max(numbers[0], numbers[1]))
                        num_idx += 1
                    elif numbers:
                        params[param_name] = numbers[num_idx] if param_type == "integer" else float(numbers[num_idx])
                        num_idx += 1
                elif "second" in param_desc or "smaller" in param_desc:
                    # Assign the smaller number
                    if len(numbers) >= 2:
                        params[param_name] = min(numbers[0], numbers[1]) if param_type == "integer" else float(min(numbers[0], numbers[1]))
                        num_idx += 1
                    elif numbers:
                        params[param_name] = numbers[num_idx] if param_type == "integer" else float(numbers[num_idx])
                        num_idx += 1
                else:
                    # Just assign in order
                    params[param_name] = numbers[num_idx] if param_type == "integer" else float(numbers[num_idx])
                    num_idx += 1
    
    return {func_name: params}
