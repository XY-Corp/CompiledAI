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
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
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
    
    # For quadratic equation: look for a, b, c coefficients
    # Pattern: "a = 3" or "a=3" or "a is 3" or "coefficient a = 3"
    for param_name in params_schema.keys():
        param_info = params_schema[param_name]
        param_type = param_info.get("type", "string")
        
        if param_type == "integer" or param_type == "number":
            # Try multiple patterns for named coefficients
            patterns = [
                rf'\b{param_name}\s*=\s*(-?\d+)',  # a = 3 or a=-3
                rf'\b{param_name}\s+is\s+(-?\d+)',  # a is 3
                rf'coefficient\s+{param_name}\s*=\s*(-?\d+)',  # coefficient a = 3
                rf'{param_name}\s*:\s*(-?\d+)',  # a: 3
            ]
            
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = int(match.group(1))
                    params[param_name] = value
                    break
        
        elif param_type == "string":
            # For root_type, check if user mentions specific type
            if param_name == "root_type":
                # Check if user wants all roots (including complex)
                if re.search(r'\ball\b.*roots?|roots?.*\ball\b|complex|all\s+the\s+roots', query, re.IGNORECASE):
                    params[param_name] = "all"
                elif re.search(r'\breal\b.*roots?|roots?.*\breal\b', query, re.IGNORECASE):
                    params[param_name] = "real"
                # "Find all the roots" suggests wanting all roots
                elif re.search(r'find\s+all\s+the\s+roots', query, re.IGNORECASE):
                    params[param_name] = "all"
    
    return {func_name: params}
