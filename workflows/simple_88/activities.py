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
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query (integers and floats)
    # Pattern matches numbers like 70, 1.75, 70kg, 1.75m
    number_patterns = re.findall(r'(\d+\.?\d*)\s*(?:kg|m|cm|lb|ft|in)?', query, re.IGNORECASE)
    numbers = [float(n) for n in number_patterns if n]
    
    # Map extracted numbers to parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "float", "number"]:
            # Try to match based on context clues in the query
            if "weight" in param_name.lower() or "weight" in param_desc:
                # Look for weight value - typically larger number or followed by kg/lb
                weight_match = re.search(r'(\d+\.?\d*)\s*(?:kg|kilograms?|lb|pounds?)?', query, re.IGNORECASE)
                if weight_match:
                    val = float(weight_match.group(1))
                    params[param_name] = int(val) if param_type == "integer" else val
            elif "height" in param_name.lower() or "height" in param_desc:
                # Look for height value - typically smaller number or followed by m/cm/ft
                height_match = re.search(r'(\d+\.?\d*)\s*(?:m|meters?|cm|centimeters?|ft|feet)?(?:\s+tall)?', query, re.IGNORECASE)
                if height_match:
                    val = float(height_match.group(1))
                    params[param_name] = int(val) if param_type == "integer" else val
    
    # If we couldn't match by context, fall back to positional assignment
    if len(params) < len([p for p, info in params_schema.items() if info.get("type") in ["integer", "float", "number"]]):
        num_idx = 0
        for param_name, param_info in params_schema.items():
            if param_name in params:
                continue
            param_type = param_info.get("type", "string")
            if param_type in ["integer", "float", "number"] and num_idx < len(numbers):
                val = numbers[num_idx]
                params[param_name] = int(val) if param_type == "integer" else val
                num_idx += 1
    
    return {func_name: params}
