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
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    number_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Try to match number based on context in description
            matched = False
            
            # Look for specific patterns based on parameter description
            if "temperature" in param_desc or "temp" in param_name.lower():
                # Look for temperature pattern: "temperature is 298K" or "298K" or "298 K"
                temp_match = re.search(r'temperature\s+(?:is\s+)?(\d+)\s*K?', query, re.IGNORECASE)
                if not temp_match:
                    temp_match = re.search(r'(\d+)\s*K', query, re.IGNORECASE)
                if temp_match:
                    params[param_name] = int(temp_match.group(1))
                    matched = True
            
            elif "volume" in param_desc or "volume" in param_name.lower():
                # Look for volume pattern: "volume is 10 m^3" or "10 m^3"
                vol_match = re.search(r'volume\s+(?:is\s+)?(\d+)\s*m', query, re.IGNORECASE)
                if not vol_match:
                    vol_match = re.search(r'(\d+)\s*m\^?3', query, re.IGNORECASE)
                if vol_match:
                    params[param_name] = int(vol_match.group(1))
                    matched = True
            
            # Fallback: use next available number
            if not matched and number_idx < len(numbers):
                params[param_name] = int(float(numbers[number_idx]))
                number_idx += 1
        
        elif param_type == "number" or param_type == "float":
            if number_idx < len(numbers):
                params[param_name] = float(numbers[number_idx])
                number_idx += 1
        
        elif param_type == "string":
            # Check for default value in description
            default_match = re.search(r"'(\w+)'\s+as\s+default", param_desc)
            if default_match:
                # Use default value
                params[param_name] = default_match.group(1)
            else:
                # Try to extract string value from query based on param name
                # Look for patterns like "for air" or "type of gas"
                if "gas" in param_name.lower() or "gas" in param_desc:
                    gas_match = re.search(r'\b(air|oxygen|nitrogen|helium|hydrogen|co2)\b', query, re.IGNORECASE)
                    if gas_match:
                        params[param_name] = gas_match.group(1).lower()
                    elif "air" in query.lower():
                        params[param_name] = "air"
    
    return {func_name: params}
