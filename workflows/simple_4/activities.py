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
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question = data["question"]
            if isinstance(question, list) and len(question) > 0:
                if isinstance(question[0], list) and len(question[0]) > 0:
                    query = question[0][0].get("content", str(prompt))
                else:
                    query = str(question[0])
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
    
    # Extract parameters using regex patterns
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        # Try multiple patterns to extract parameter value
        value = None
        
        # Pattern 1: "param_name=value" or "param_name = value"
        pattern1 = rf'{param_name}\s*=\s*(-?\d+(?:\.\d+)?)'
        match = re.search(pattern1, query, re.IGNORECASE)
        if match:
            value = match.group(1)
        
        # Pattern 2: "param_name is value" or "param_name: value"
        if value is None:
            pattern2 = rf'{param_name}\s*(?:is|:)\s*(-?\d+(?:\.\d+)?)'
            match = re.search(pattern2, query, re.IGNORECASE)
            if match:
                value = match.group(1)
        
        # Pattern 3: For single-letter params like a, b, c - "a=2" or "a is 2"
        if value is None and len(param_name) == 1:
            pattern3 = rf'\b{param_name}\s*=\s*(-?\d+(?:\.\d+)?)'
            match = re.search(pattern3, query)
            if match:
                value = match.group(1)
        
        # Convert to appropriate type
        if value is not None:
            if param_type == "integer":
                try:
                    params[param_name] = int(value)
                except ValueError:
                    params[param_name] = int(float(value))
            elif param_type in ["number", "float"]:
                params[param_name] = float(value)
            else:
                params[param_name] = value
    
    # If we didn't find all params, try extracting all numbers in order
    if len(params) < len(params_schema):
        # Extract all numbers from query
        all_numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
        
        # Map numbers to missing params in order
        num_idx = 0
        for param_name, param_info in params_schema.items():
            if param_name not in params and num_idx < len(all_numbers):
                param_type = param_info.get("type", "string")
                value = all_numbers[num_idx]
                
                if param_type == "integer":
                    try:
                        params[param_name] = int(value)
                    except ValueError:
                        params[param_name] = int(float(value))
                elif param_type in ["number", "float"]:
                    params[param_name] = float(value)
                else:
                    params[param_name] = value
                
                num_idx += 1
    
    return {func_name: params}
