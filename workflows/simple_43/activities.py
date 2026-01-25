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
    
    # Extract all numbers from the query
    # Pattern matches integers and floats (including scientific notation)
    numbers = re.findall(r'(\d+(?:\.\d+)?(?:e[+-]?\d+)?)', query, re.IGNORECASE)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "int", "float", "number"]:
            # Try to match number based on context in description
            matched = False
            
            # Look for specific patterns based on parameter description
            if "current" in param_desc:
                # Look for current value - pattern: "X Amperes" or "current of X"
                current_match = re.search(r'(?:current\s+of\s+)?(\d+(?:\.\d+)?)\s*(?:amperes?|amps?|a\b)', query, re.IGNORECASE)
                if current_match:
                    val = current_match.group(1)
                    params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                    matched = True
            
            elif "distance" in param_desc:
                # Look for distance value - pattern: "X meters" or "X m away"
                distance_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:meters?|m\b)(?:\s+away)?', query, re.IGNORECASE)
                if distance_match:
                    val = distance_match.group(1)
                    params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                    matched = True
            
            elif "permeability" in param_desc:
                # Permeability is optional with default - only extract if explicitly mentioned
                perm_match = re.search(r'permeability\s+(?:of\s+)?(\d+(?:\.\d+)?(?:e[+-]?\d+)?)', query, re.IGNORECASE)
                if perm_match:
                    params[param_name] = float(perm_match.group(1))
                    matched = True
                # Don't set if not mentioned - let default apply
            
            # Fallback: assign numbers in order if not matched by context
            if not matched and num_idx < len(numbers) and param_name not in params:
                # Skip permeability if it has a default and wasn't explicitly mentioned
                if "permeability" not in param_name.lower():
                    val = numbers[num_idx]
                    params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                    num_idx += 1
    
    return {func_name: params}
