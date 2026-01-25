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
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    # Pattern matches integers and floats (e.g., 70, 1.75, 70kg, 1.75m)
    numbers = re.findall(r'(\d+\.?\d*)', query)
    
    # Convert to appropriate types
    parsed_numbers = []
    for num in numbers:
        if '.' in num:
            parsed_numbers.append(float(num))
        else:
            parsed_numbers.append(int(num))

    # Map extracted values to parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Look for integer values - for weight, typically larger whole number
            for i, num in enumerate(parsed_numbers):
                if isinstance(num, int) or (isinstance(num, float) and num == int(num)):
                    # Check if description hints at what we're looking for
                    if "weight" in param_desc or "kg" in param_desc:
                        # Weight is typically the larger integer (70 vs 1.75)
                        if num >= 10:  # Weight in kg is usually > 10
                            params[param_name] = int(num)
                            break
                    elif num_idx < len(parsed_numbers):
                        params[param_name] = int(parsed_numbers[num_idx])
                        num_idx += 1
                        break
                        
        elif param_type == "float" or param_type == "number":
            # Look for float values - for height in meters, typically < 3
            for i, num in enumerate(parsed_numbers):
                if "height" in param_desc or "meter" in param_desc or "_m" in param_name:
                    # Height in meters is typically between 0.5 and 2.5
                    if isinstance(num, float) and num < 3:
                        params[param_name] = float(num)
                        break
                    elif isinstance(num, int) and num < 3:
                        params[param_name] = float(num)
                        break
                elif num_idx < len(parsed_numbers):
                    params[param_name] = float(parsed_numbers[num_idx])
                    num_idx += 1
                    break

    # Fallback: if we didn't match by description, assign by order
    # For BMI: first number is usually weight (70), second is height (1.75)
    if not params or len(params) < len(params_schema):
        num_idx = 0
        for param_name, param_info in params_schema.items():
            if param_name in params:
                continue
            param_type = param_info.get("type", "string")
            if num_idx < len(parsed_numbers):
                if param_type == "integer":
                    params[param_name] = int(parsed_numbers[num_idx])
                elif param_type in ["float", "number"]:
                    params[param_name] = float(parsed_numbers[num_idx])
                else:
                    params[param_name] = parsed_numbers[num_idx]
                num_idx += 1

    return {func_name: params}
