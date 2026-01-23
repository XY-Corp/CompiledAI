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
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
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
    required_params = func.get("parameters", {}).get("required", [])

    # Extract parameters using regex
    params = {}
    
    # Extract all numbers with optional units from the query
    # Pattern matches: "6cm", "10cm", "6 cm", "10 cm", "6", "10"
    number_patterns = re.findall(r'(\d+(?:\.\d+)?)\s*(cm|m|mm|in|ft|inch|inches|feet|meters|centimeters)?', query, re.IGNORECASE)
    
    # Also try to extract numbers with context (e.g., "base ... 6cm", "height ... 10cm")
    base_match = re.search(r'base[^\d]*(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    height_match = re.search(r'height[^\d]*(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    
    # Extract unit if present
    unit_match = re.search(r'(\d+)\s*(cm|m|mm|in|ft|inch|inches|feet|meters|centimeters)', query, re.IGNORECASE)
    unit = unit_match.group(2).lower() if unit_match else None
    
    # Map extracted values to parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "base":
            if base_match:
                value = base_match.group(1)
            elif number_patterns and len(number_patterns) >= 1:
                # First number is typically base
                value = number_patterns[0][0]
            else:
                continue
            
            if param_type == "integer":
                params[param_name] = int(float(value))
            elif param_type in ["number", "float"]:
                params[param_name] = float(value)
            else:
                params[param_name] = value
                
        elif param_name == "height":
            if height_match:
                value = height_match.group(1)
            elif number_patterns and len(number_patterns) >= 2:
                # Second number is typically height
                value = number_patterns[1][0]
            else:
                continue
            
            if param_type == "integer":
                params[param_name] = int(float(value))
            elif param_type in ["number", "float"]:
                params[param_name] = float(value)
            else:
                params[param_name] = value
                
        elif param_name == "unit":
            # Only include unit if explicitly found in query
            if unit:
                params[param_name] = unit

    return {func_name: params}
