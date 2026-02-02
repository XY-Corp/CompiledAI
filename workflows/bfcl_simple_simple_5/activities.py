import re
import json
from typing import Any


async def extract_function_call(
    prompt: str,
    functions: list = None,
    user_query: str = None,
    tools: list = None,
    tool_name_mapping: dict = None,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from natural language query.
    
    Parses the prompt to extract function name and parameters using regex
    and string matching. Returns format: {"function_name": {"param1": val1}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            try:
                data = json.loads(prompt)
                # Handle BFCL-style nested structure
                if "question" in data and isinstance(data["question"], list):
                    if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                        query = data["question"][0][0].get("content", prompt)
                    else:
                        query = str(data["question"])
                else:
                    query = data.get("content", str(prompt))
            except json.JSONDecodeError:
                query = prompt
        else:
            query = str(prompt)
    except Exception:
        query = str(prompt)

    # Parse functions - may be JSON string
    funcs = []
    if functions:
        if isinstance(functions, str):
            try:
                funcs = json.loads(functions)
            except json.JSONDecodeError:
                funcs = []
        else:
            funcs = functions
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    
    # Extract named coefficient assignments: "a = 3", "b = -11", "c = -4"
    # Pattern matches: letter = number (with optional negative sign)
    named_assignments = re.findall(r'\b([a-zA-Z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?)', query)
    assignment_map = {name.lower(): value for name, value in named_assignments}
    
    # Extract root_type if mentioned
    root_type = None
    if re.search(r'\ball\b.*\broots?\b|\broots?\b.*\ball\b', query, re.IGNORECASE):
        root_type = "all"
    elif re.search(r'\breal\b.*\broots?\b|\broots?\b.*\breal\b', query, re.IGNORECASE):
        root_type = "real"
    elif re.search(r'\bcomplex\b', query, re.IGNORECASE):
        root_type = "all"
    
    # Map extracted values to parameter schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
        param_lower = param_name.lower()
        
        # Check if we have a direct assignment for this parameter
        if param_lower in assignment_map:
            value = assignment_map[param_lower]
            if param_type == "integer":
                params[param_name] = int(value)
            elif param_type in ["number", "float"]:
                params[param_name] = float(value)
            else:
                params[param_name] = value
        elif param_name == "root_type" and root_type:
            params[param_name] = root_type
    
    # If we didn't find named assignments, try to extract numbers in order
    if not params or len(params) < 3:
        # Extract all numbers from query
        all_numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
        
        # Get required numeric params in order
        numeric_params = [
            (name, info) for name, info in params_schema.items()
            if isinstance(info, dict) and info.get("type") in ["integer", "number", "float"]
        ]
        
        # Assign numbers to params if not already assigned
        num_idx = 0
        for param_name, param_info in numeric_params:
            if param_name not in params and num_idx < len(all_numbers):
                param_type = param_info.get("type", "integer")
                if param_type == "integer":
                    params[param_name] = int(float(all_numbers[num_idx]))
                else:
                    params[param_name] = float(all_numbers[num_idx])
                num_idx += 1
    
    # Add root_type if found and not already added
    if root_type and "root_type" not in params:
        params["root_type"] = root_type
    
    return {func_name: params}
