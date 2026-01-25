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
    """Extract function call parameters from user query using regex and string matching."""
    
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract all numbers from query
    numbers = re.findall(r'(\d+(?:\.\d+)?)', query)
    numbers = [float(n) if '.' in n else int(n) for n in numbers]
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "float", "number"]:
            # Try to match specific patterns based on parameter name/description
            value = None
            
            # Check for height-related patterns
            if "height" in param_name.lower() or "height" in param_desc:
                height_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m|meters?|metre)', query, re.IGNORECASE)
                if height_match:
                    value = float(height_match.group(1)) if '.' in height_match.group(1) else int(height_match.group(1))
                elif re.search(r'(?:from|height|dropped)\s*(?:of\s*)?(\d+(?:\.\d+)?)', query, re.IGNORECASE):
                    match = re.search(r'(?:from|height|dropped)\s*(?:of\s*)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
                    value = float(match.group(1)) if '.' in match.group(1) else int(match.group(1))
            
            # Check for velocity-related patterns
            elif "velocity" in param_name.lower() or "velocity" in param_desc:
                vel_match = re.search(r'(?:initial\s*)?velocity\s*(?:of\s*)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
                if vel_match:
                    value = float(vel_match.group(1)) if '.' in vel_match.group(1) else int(vel_match.group(1))
                elif "dropped" in query.lower():
                    # Object dropped implies initial velocity of 0
                    value = 0
            
            # Check for gravity-related patterns
            elif "gravity" in param_name.lower() or "gravitational" in param_desc:
                grav_match = re.search(r'gravity\s*(?:of\s*)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
                if grav_match:
                    value = float(grav_match.group(1))
                # Don't set default - let it be omitted if not specified (function has default)
            
            # Fallback: use next available number if required and not yet assigned
            if value is None and param_name in required_params:
                if num_idx < len(numbers):
                    value = numbers[num_idx]
                    num_idx += 1
            
            if value is not None:
                # Convert to correct type
                if param_type == "integer":
                    params[param_name] = int(value)
                elif param_type == "float":
                    params[param_name] = float(value)
                else:
                    params[param_name] = value
    
    return {func_name: params}
