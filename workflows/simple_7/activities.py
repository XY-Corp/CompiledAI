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
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers from query
            # Look for patterns like "radius of 4" or "4 inches" or just numbers
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
            if numbers:
                # For radius/diameter/size type params, take the first number
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Check if this is a unit parameter
            if "unit" in param_name.lower() or "unit" in param_desc:
                # Look for common units in the query
                unit_patterns = [
                    (r'\b(inches|inch|in)\b', 'inches'),
                    (r'\b(centimeters|centimeter|cm)\b', 'cm'),
                    (r'\b(meters|meter|m)\b', 'm'),
                    (r'\b(feet|foot|ft)\b', 'feet'),
                    (r'\b(millimeters|millimeter|mm)\b', 'mm'),
                    (r'\b(kilometers|kilometer|km)\b', 'km'),
                    (r'\b(miles|mile|mi)\b', 'miles'),
                    (r'\b(yards|yard|yd)\b', 'yards'),
                ]
                
                for pattern, unit_value in unit_patterns:
                    if re.search(pattern, query, re.IGNORECASE):
                        params[param_name] = unit_value
                        break
                
                # If no unit found and not required, skip (use default)
                if param_name not in params and param_name not in required_params:
                    continue
            else:
                # Generic string extraction - look for quoted strings or key phrases
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
    
    return {func_name: params}
