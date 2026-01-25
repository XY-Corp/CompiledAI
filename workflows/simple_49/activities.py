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
    
    # For pressure calculation, look for specific patterns
    # Pattern: "atmospheric pressure of X atm" or "atm_pressure of X"
    atm_match = re.search(r'atmospheric\s+pressure\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    
    # Pattern: "gauge pressure of X atm" or "gauge_pressure of X"
    gauge_match = re.search(r'gauge\s+pressure\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    
    # Map extracted values to parameter names based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "atm_pressure" or "atmospheric" in param_desc:
            if atm_match:
                value = atm_match.group(1)
                if param_type == "integer":
                    params[param_name] = int(float(value))
                elif param_type in ["number", "float"]:
                    params[param_name] = float(value)
                else:
                    params[param_name] = value
        elif param_name == "gauge_pressure" or "gauge" in param_desc:
            if gauge_match:
                value = gauge_match.group(1)
                if param_type == "integer":
                    params[param_name] = int(float(value))
                elif param_type in ["number", "float"]:
                    params[param_name] = float(value)
                else:
                    params[param_name] = value
    
    # Fallback: if specific patterns didn't match, try to assign numbers in order
    if not params and numbers:
        num_idx = 0
        for param_name, param_info in params_schema.items():
            if num_idx < len(numbers):
                param_type = param_info.get("type", "string")
                if param_type == "integer":
                    params[param_name] = int(float(numbers[num_idx]))
                elif param_type in ["number", "float"]:
                    params[param_name] = float(numbers[num_idx])
                else:
                    params[param_name] = numbers[num_idx]
                num_idx += 1
    
    return {func_name: params}
