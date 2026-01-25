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
    """Extract function call parameters from user query using regex patterns.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - handle JSON string or raw string
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
        query = str(prompt)
    
    # Parse functions - handle JSON string or list
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            if num_idx < len(numbers):
                if param_type == "integer":
                    params[param_name] = int(float(numbers[num_idx]))
                else:
                    params[param_name] = float(numbers[num_idx])
                num_idx += 1
        elif param_type == "string":
            # Check if there's a default mentioned in description
            description = param_info.get("description", "")
            default_match = re.search(r'[Dd]efault\s+(?:is\s+)?["\']?([^"\'\.]+)["\']?', description)
            
            # Look for explicit unit mentions in query
            unit_patterns = [
                r'in\s+(\w+(?:/\w+)?)',  # "in kg/m³"
                r'unit[s]?\s+(?:is|are|:)?\s*(\w+(?:/\w+)?)',  # "unit is kg/m³"
            ]
            
            unit_found = None
            for pattern in unit_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    unit_found = match.group(1)
                    break
            
            # Only include if explicitly mentioned in query, otherwise skip optional params
            if unit_found:
                params[param_name] = unit_found
            # Don't include default values for optional parameters
    
    return {func_name: params}
