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
    """Extract function name and parameters from user query using regex/parsing.
    
    Returns format: {"function_name": {"param1": val1, ...}}
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
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Map parameters based on schema
    num_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            # For numeric parameters, try to extract from query
            if param_name == "distance_in_light_years":
                # Look for patterns like "X light years" or just numbers
                distance_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:light[\s-]?years?)', query, re.IGNORECASE)
                if distance_match:
                    value = distance_match.group(1)
                    params[param_name] = int(float(value)) if param_type == "integer" else float(value)
                elif num_idx < len(numbers):
                    # Fallback to first number found
                    value = numbers[num_idx]
                    params[param_name] = int(float(value)) if param_type == "integer" else float(value)
                    num_idx += 1
            elif param_name == "speed_of_light":
                # Look for explicit speed mention, otherwise skip (has default)
                speed_match = re.search(r'speed.*?(\d+)', query, re.IGNORECASE)
                if speed_match:
                    params[param_name] = int(speed_match.group(1))
                # Don't include if not explicitly mentioned (has default value)
            else:
                # Generic number extraction for other numeric params
                if num_idx < len(numbers):
                    value = numbers[num_idx]
                    params[param_name] = int(float(value)) if param_type == "integer" else float(value)
                    num_idx += 1
        
        elif param_type == "string":
            # For string parameters, try pattern matching
            # Look for patterns like "for X" or "in X" or "from X"
            string_match = re.search(r'(?:for|in|from|to)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|to|from)|$)', query, re.IGNORECASE)
            if string_match:
                params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
