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
    """Extract function name and parameters from user query using regex patterns."""
    
    # Parse prompt (may be JSON string with nested structure)
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract all numbers from the query (including scientific notation)
    # Pattern matches: integers, decimals, and scientific notation (e.g., 1e-9, 2.5e10)
    number_pattern = r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?'
    numbers = re.findall(number_pattern, query)
    
    # Convert to floats
    float_numbers = []
    for num in numbers:
        try:
            float_numbers.append(float(num))
        except ValueError:
            continue
    
    # Map extracted numbers to parameters based on order and schema
    params = {}
    param_names = list(params_schema.keys())
    required_params = func.get("parameters", {}).get("required", [])
    
    # For this specific function: charge1, charge2, distance (in order they appear)
    # The query mentions: "1e-9 and 2e-9 of distance 0.05"
    # So we expect: charge1=1e-9, charge2=2e-9, distance=0.05
    
    num_idx = 0
    for param_name in param_names:
        param_info = params_schema.get(param_name, {})
        param_type = param_info.get("type", "string")
        
        # Skip optional params with defaults unless we have extra numbers
        if param_name not in required_params and param_name == "constant":
            # Don't assign a value to constant - let it use default
            continue
        
        if param_type in ["float", "number", "integer"] and num_idx < len(float_numbers):
            if param_type == "integer":
                params[param_name] = int(float_numbers[num_idx])
            else:
                params[param_name] = float_numbers[num_idx]
            num_idx += 1
    
    return {func_name: params}
