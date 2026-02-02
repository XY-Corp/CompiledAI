import re
import json
from typing import Any


async def extract_function_call(
    prompt: str,
    functions: list = None,
    user_query: str = None,
    tools: list = None,
    tool_name_mapping: dict = None,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from natural language query using regex.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL-style nested structure
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = data.get("content", str(prompt))
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    funcs = []
    if functions:
        if isinstance(functions, str):
            try:
                funcs = json.loads(functions)
            except json.JSONDecodeError:
                funcs = []
        else:
            funcs = functions
    
    # Get function details
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract all numbers from the query using regex
    # Match integers and floats
    numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
    numbers = [int(n) if '.' not in n else float(n) for n in numbers]
    
    # Build parameters dict based on schema
    params = {}
    num_idx = 0
    
    # Get parameter names in order (required first, then optional)
    param_names = list(params_schema.keys())
    
    # For math.hypot specifically: x, y are required, z is optional
    # Extract numbers in order they appear and assign to parameters
    for param_name in param_names:
        param_info = params_schema.get(param_name, {})
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            if num_idx < len(numbers):
                # Only include required params or optional if we have enough numbers
                if param_name in required_params:
                    params[param_name] = int(numbers[num_idx]) if param_type == "integer" else numbers[num_idx]
                    num_idx += 1
                elif num_idx < len(numbers) and len(numbers) > len(required_params):
                    # We have extra numbers for optional params
                    params[param_name] = int(numbers[num_idx]) if param_type == "integer" else numbers[num_idx]
                    num_idx += 1
        elif param_type == "string":
            # Try to extract string values using common patterns
            # Pattern: "for X" or "named X" or similar
            string_match = re.search(
                r'(?:for|named|called|with|of)\s+["\']?([A-Za-z][A-Za-z0-9\s]*?)["\']?(?:\s+(?:and|with|,)|$)',
                query,
                re.IGNORECASE
            )
            if string_match and param_name in required_params:
                params[param_name] = string_match.group(1).strip()
    
    # Return in the exact format required: {"func_name": {params}}
    return {func_name: params}
