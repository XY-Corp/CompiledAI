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
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        # Try to find named parameter pattern: "param_name=value" or "param_name = value"
        named_pattern = rf'{param_name}\s*=\s*(-?\d+(?:\.\d+)?)'
        named_match = re.search(named_pattern, query, re.IGNORECASE)
        
        if named_match:
            value_str = named_match.group(1)
            if param_type == "integer":
                params[param_name] = int(value_str)
            elif param_type in ["number", "float"]:
                params[param_name] = float(value_str)
            else:
                params[param_name] = value_str
    
    # If we didn't find all params with named patterns, try positional extraction
    if len(params) < len(params_schema):
        # Extract all numbers from the query
        all_numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
        
        # Map numbers to parameters in order (for params not yet found)
        num_idx = 0
        for param_name, param_info in params_schema.items():
            if param_name in params:
                continue  # Already found via named pattern
                
            param_type = param_info.get("type", "string")
            
            if param_type in ["integer", "number", "float"] and num_idx < len(all_numbers):
                value_str = all_numbers[num_idx]
                if param_type == "integer":
                    params[param_name] = int(float(value_str))
                else:
                    params[param_name] = float(value_str)
                num_idx += 1
            elif param_type == "string":
                # Try to extract string values
                string_match = re.search(r'(?:for|in|of|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,)|$)', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()

    return {func_name: params}
