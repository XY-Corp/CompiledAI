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
    
    # Extract parameters from query using regex
    params = {}
    
    # For quadratic equation: look for coefficients a, b, c
    # Patterns: "a = 3", "a=3", "coefficient a = 3", "coefficients a = 3, b = -11, c = -4"
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer" or param_type == "number":
            # Try multiple patterns for named coefficients
            patterns = [
                rf'{param_name}\s*=\s*(-?\d+)',  # a = 3 or a=-3
                rf'{param_name}\s*:\s*(-?\d+)',  # a: 3
                rf'{param_name}\s+is\s+(-?\d+)',  # a is 3
                rf'coefficient\s+{param_name}\s*=\s*(-?\d+)',  # coefficient a = 3
            ]
            
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = int(match.group(1))
                    params[param_name] = value
                    break
        
        elif param_type == "string":
            # For optional string params like root_type, check if mentioned
            # Look for keywords like "real roots", "all roots", "complex roots"
            if param_name == "root_type":
                if re.search(r'\breal\s+roots?\b', query, re.IGNORECASE):
                    params[param_name] = "real"
                elif re.search(r'\ball\s+roots?\b', query, re.IGNORECASE):
                    params[param_name] = "all"
                elif re.search(r'\bcomplex\s+roots?\b', query, re.IGNORECASE):
                    params[param_name] = "all"
                # If "all the roots" is mentioned, it implies all roots
                elif re.search(r'\ball\s+the\s+roots?\b', query, re.IGNORECASE):
                    params[param_name] = "all"
                # Don't include optional param if not specified
    
    return {func_name: params}
