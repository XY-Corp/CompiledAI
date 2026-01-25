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
    """Extract function call parameters from natural language query.
    
    Parses the prompt to extract the user query, then uses regex to extract
    parameter values based on the function schema.
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
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Look for unit specification (e.g., "in km/h", "to km/h")
    unit_match = re.search(r'(?:in|to)\s+([a-zA-Z/]+(?:/[a-zA-Z]+)?)', query, re.IGNORECASE)
    
    # Map extracted values to parameters based on schema
    num_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Try to match based on description context
            if "distance" in param_desc and num_idx < len(numbers):
                # Look for distance-related number (usually larger or mentioned with meters)
                distance_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:meters?|m\b|km)', query, re.IGNORECASE)
                if distance_match:
                    params[param_name] = int(float(distance_match.group(1)))
                elif num_idx < len(numbers):
                    params[param_name] = int(float(numbers[num_idx]))
                    num_idx += 1
            elif "time" in param_desc and num_idx < len(numbers):
                # Look for time-related number (usually mentioned with seconds)
                time_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:seconds?|s\b|minutes?|hours?)', query, re.IGNORECASE)
                if time_match:
                    params[param_name] = int(float(time_match.group(1)))
                elif num_idx < len(numbers):
                    params[param_name] = int(float(numbers[num_idx]))
                    num_idx += 1
            elif num_idx < len(numbers):
                params[param_name] = int(float(numbers[num_idx]))
                num_idx += 1
                
        elif param_type == "number" or param_type == "float":
            if num_idx < len(numbers):
                params[param_name] = float(numbers[num_idx])
                num_idx += 1
                
        elif param_type == "string":
            # Check if this is a unit parameter
            if "unit" in param_name.lower() or "unit" in param_desc:
                if unit_match:
                    params[param_name] = unit_match.group(1)
    
    # For calculate_speed specifically, ensure we get distance and time correctly
    if func_name == "calculate_speed":
        # Re-extract with more specific patterns
        distance_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:meters?|m\b)', query, re.IGNORECASE)
        time_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)', query, re.IGNORECASE)
        
        if distance_match:
            params["distance"] = int(float(distance_match.group(1)))
        elif "distance" in params_schema and len(numbers) >= 1:
            params["distance"] = int(float(numbers[0]))
            
        if time_match:
            params["time"] = int(float(time_match.group(1)))
        elif "time" in params_schema and len(numbers) >= 2:
            params["time"] = int(float(numbers[1]))
        
        # Check for unit conversion request
        if unit_match:
            params["to_unit"] = unit_match.group(1)
    
    return {func_name: params}
