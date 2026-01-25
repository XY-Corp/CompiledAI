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
    
    Returns a dict with function name as key and parameters as nested object.
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
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    number_idx = 0
    
    # Map parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            # Try to find contextual match first (e.g., "base 6" or "height 10")
            contextual_pattern = rf'{param_name}\s*(?:of|is|=|:)?\s*(\d+(?:\.\d+)?)'
            contextual_match = re.search(contextual_pattern, query, re.IGNORECASE)
            
            if contextual_match:
                value = contextual_match.group(1)
                if param_type == "integer":
                    params[param_name] = int(float(value))
                else:
                    params[param_name] = float(value)
            elif number_idx < len(numbers):
                # Fall back to sequential number extraction
                value = numbers[number_idx]
                if param_type == "integer":
                    params[param_name] = int(float(value))
                else:
                    params[param_name] = float(value)
                number_idx += 1
        
        elif param_type == "string":
            # Try to extract string value contextually
            contextual_pattern = rf'{param_name}\s*(?:of|is|=|:)?\s*["\']?([a-zA-Z\s]+)["\']?'
            contextual_match = re.search(contextual_pattern, query, re.IGNORECASE)
            
            if contextual_match:
                params[param_name] = contextual_match.group(1).strip()
            # Only include optional string params if explicitly mentioned
    
    return {func_name: params}
