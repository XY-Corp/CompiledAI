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
    
    Parses the user query to extract parameter values and returns them
    in the format {"function_name": {"param1": val1, ...}}.
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
                query = data["question"][0][0].get("content", str(prompt))
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract all numbers from the query
    # Pattern matches integers and floats (including scientific notation)
    numbers = re.findall(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', query)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "int", "float", "number"]:
            # Try to find a contextual match first based on description keywords
            value = None
            
            # Look for specific patterns based on parameter description
            if "charge" in param_desc or "coulomb" in param_desc:
                # Look for charge value - pattern: "X coulombs" or "charge of X"
                charge_match = re.search(r'(?:charge\s+of\s+|a\s+charge\s+of\s+)?(\d+(?:\.\d+)?)\s*(?:coulombs?|C\b)', query, re.IGNORECASE)
                if charge_match:
                    value = charge_match.group(1)
            
            elif "distance" in param_desc or "meter" in param_desc:
                # Look for distance value - pattern: "X meters" or "distance of X"
                dist_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:meters?|m\b)', query, re.IGNORECASE)
                if dist_match:
                    value = dist_match.group(1)
            
            elif "permitivity" in param_desc or "permittivity" in param_desc:
                # Look for permitivity value - usually scientific notation
                perm_match = re.search(r'permitivity\s+(?:of\s+)?(\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)', query, re.IGNORECASE)
                if perm_match:
                    value = perm_match.group(1)
            
            # If no contextual match, use sequential number extraction
            if value is None and num_idx < len(numbers):
                value = numbers[num_idx]
                num_idx += 1
            
            # Convert to appropriate type
            if value is not None:
                if param_type == "integer" or param_type == "int":
                    params[param_name] = int(float(value))
                else:  # float or number
                    params[param_name] = float(value)
        
        elif param_type == "string":
            # Extract string values based on context
            # This is a fallback - most physics calculations use numbers
            string_match = re.search(r'(?:for|in|of|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|at)|$)', query, re.IGNORECASE)
            if string_match:
                params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
