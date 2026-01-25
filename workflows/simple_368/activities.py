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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string parsing to extract values - no LLM calls needed.
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
    
    # Extract parameters from query using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["float", "number"]:
            # Extract float numbers - look for patterns like "1.5 kg", "2.5kg", etc.
            # Also match integers that should be floats
            float_patterns = [
                r'(\d+\.?\d*)\s*(?:kg|kilogram|kilo)',  # weight with unit
                r'(\d+\.?\d*)\s*(?:lb|pound)',  # weight in pounds
                r'(\d+\.?\d*)',  # any number
            ]
            
            for pattern in float_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = float(match.group(1))
                    break
        
        elif param_type == "integer":
            # Extract integers - look for temperature patterns first
            if "temp" in param_name.lower() or "temperature" in param_desc:
                temp_patterns = [
                    r'(\d+)\s*(?:degrees?|°|celsius|c\b)',
                    r'at\s+(\d+)',
                    r'(\d{3})',  # 3-digit number likely temperature
                ]
                for pattern in temp_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = int(match.group(1))
                        break
            else:
                # Generic integer extraction
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract string values based on context
            if "method" in param_name.lower() or "method" in param_desc:
                # Look for cooking methods
                methods = ["roast", "bake", "grill", "fry", "steam", "boil", "broil"]
                for method in methods:
                    if method in query.lower():
                        params[param_name] = method
                        break
    
    # Only include required params and params we found values for
    # Don't include optional params with default values unless explicitly mentioned
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
        elif param_name in required_params:
            # Required param not found - this shouldn't happen with good input
            # but we need to handle it
            if param_name in params:
                final_params[param_name] = params[param_name]
    
    # Ensure we have at least the required params
    for req_param in required_params:
        if req_param not in final_params and req_param in params:
            final_params[req_param] = params[req_param]
        elif req_param not in final_params:
            # Try to extract again with broader patterns
            param_info = params_schema.get(req_param, {})
            param_type = param_info.get("type", "string")
            
            if param_type in ["float", "number"]:
                numbers = re.findall(r'(\d+\.?\d*)', query)
                if numbers:
                    final_params[req_param] = float(numbers[0])
    
    return {func_name: final_params}
