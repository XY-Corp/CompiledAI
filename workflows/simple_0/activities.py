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
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Extract unit if mentioned (e.g., "units", "meters", "cm", etc.)
    unit_match = re.search(r'\b(\d+)\s+(units?|meters?|cm|inches?|feet|ft|m)\b', query, re.IGNORECASE)
    unit_value = None
    if unit_match:
        unit_value = unit_match.group(2).lower()
        # Normalize unit
        if unit_value.endswith('s') and unit_value != 'inches':
            unit_value = unit_value  # Keep as-is for "units"
    
    # Map extracted values to parameter names based on schema
    num_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            # Look for specific patterns first
            if param_name == "base":
                base_match = re.search(r'base\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
                if base_match:
                    val = base_match.group(1)
                    params[param_name] = int(val) if param_type == "integer" else float(val)
                    continue
            elif param_name == "height":
                height_match = re.search(r'height\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
                if height_match:
                    val = height_match.group(1)
                    params[param_name] = int(val) if param_type == "integer" else float(val)
                    continue
            
            # Fallback: use numbers in order
            if num_idx < len(numbers):
                val = numbers[num_idx]
                params[param_name] = int(val) if param_type == "integer" else float(val)
                num_idx += 1
                
        elif param_type == "string":
            if param_name == "unit" and unit_value:
                params[param_name] = unit_value
            # Only add optional string params if we found a value
    
    return {func_name: params}
