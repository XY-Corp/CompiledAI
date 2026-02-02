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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex to extract parameter values - NO LLM calls needed since values are explicit in text.
    """
    # Parse prompt - may be JSON string with nested structure (BFCL format)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL nested format: {"question": [[{"content": "..."}]]}
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

    # Parse functions list - may be JSON string
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
    
    # Handle both "parameters.properties" and "parameters" directly
    params_schema = func.get("parameters", {})
    if "properties" in params_schema:
        props = params_schema.get("properties", {})
    else:
        props = params_schema
    
    # Extract parameter values using regex
    params = {}
    
    for param_name, param_info in props.items():
        # Determine parameter type
        if isinstance(param_info, str):
            param_type = param_info
        else:
            param_type = param_info.get("type", "string")
        
        # Try multiple patterns to extract the value for this parameter
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
        
        # Pattern 3: "param_name of value" (e.g., "coefficient of 5")
        if value is None:
            pattern3 = rf'{param_name}\s+of\s+(-?\d+(?:\.\d+)?)'
            match = re.search(pattern3, query, re.IGNORECASE)
            if match:
                value = match.group(1)
        
        # Convert to appropriate type
        if value is not None:
            if param_type == "integer":
                params[param_name] = int(float(value))
            elif param_type in ["float", "number"]:
                params[param_name] = float(value)
            else:
                params[param_name] = value
    
    # If we couldn't extract all required params with named patterns,
    # try extracting all numbers in order and mapping to params
    if len(params) < len(props):
        # Extract all numbers from the query
        all_numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
        
        # Map numbers to parameters that weren't found
        num_idx = 0
        for param_name, param_info in props.items():
            if param_name not in params and num_idx < len(all_numbers):
                if isinstance(param_info, str):
                    param_type = param_info
                else:
                    param_type = param_info.get("type", "string")
                
                if param_type == "integer":
                    params[param_name] = int(float(all_numbers[num_idx]))
                elif param_type in ["float", "number"]:
                    params[param_name] = float(all_numbers[num_idx])
                else:
                    params[param_name] = all_numbers[num_idx]
                num_idx += 1
    
    return {func_name: params}
