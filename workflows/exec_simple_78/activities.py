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
    
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            # Extract array from query - look for [...]
            array_match = re.search(r'\[([^\]]+)\]', query)
            if array_match:
                array_str = array_match.group(1)
                # Parse array elements
                items_type = param_info.get("items", {}).get("type", "string")
                if items_type == "integer":
                    # Extract integers from the array string
                    numbers = re.findall(r'-?\d+', array_str)
                    params[param_name] = [int(n) for n in numbers]
                elif items_type == "number":
                    numbers = re.findall(r'-?\d+\.?\d*', array_str)
                    params[param_name] = [float(n) for n in numbers]
                else:
                    # String items - split by comma
                    items = [item.strip().strip('"\'') for item in array_str.split(',')]
                    params[param_name] = items
        
        elif param_type == "boolean":
            # Check for boolean indicators in query
            param_desc = param_info.get("description", "").lower()
            
            # Check for descending/reverse indicators
            if "descending" in param_desc or "reverse" in param_desc:
                # Look for descending, reverse, desc keywords in query
                if re.search(r'\b(descending|reverse|desc)\b', query, re.IGNORECASE):
                    params[param_name] = True
                else:
                    # Check if default is provided and use it, otherwise False
                    if "default" in param_info:
                        params[param_name] = param_info["default"]
                    # Only set if explicitly mentioned or required
                    elif re.search(r'\b(ascending|asc)\b', query, re.IGNORECASE):
                        params[param_name] = False
                    else:
                        # Descending mentioned in query context
                        if "descending" in query.lower():
                            params[param_name] = True
            else:
                # Generic boolean - look for true/false, yes/no
                if re.search(r'\b(true|yes)\b', query, re.IGNORECASE):
                    params[param_name] = True
                elif re.search(r'\b(false|no)\b', query, re.IGNORECASE):
                    params[param_name] = False
        
        elif param_type == "integer":
            # Extract first integer
            numbers = re.findall(r'-?\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "number":
            # Extract first number (float)
            numbers = re.findall(r'-?\d+\.?\d*', query)
            if numbers:
                params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # For string params, try to extract based on description context
            # This is a fallback - specific patterns should be added as needed
            pass
    
    return {func_name: params}
