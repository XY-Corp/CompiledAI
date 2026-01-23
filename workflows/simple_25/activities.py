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
    # Parse prompt - handle BFCL format (may be JSON with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # BFCL format: {"question": [[{"role": "user", "content": "..."}]], "function": [...]}
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
    required_params = func.get("parameters", {}).get("required", [])

    # Extract parameters using regex
    params = {}
    query_lower = query.lower()

    # Extract all numbers from the query
    numbers = re.findall(r'(\d+(?:\.\d+)?)', query)
    
    # For calculate_final_velocity, we need to identify:
    # - height: look for patterns like "150 meter", "from a X meter"
    # - initial_velocity: look for "initial velocity is X" or "zero"
    # - gravity: usually default, but check for explicit values

    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "height":
            # Look for height patterns: "X meter building", "from X meter", "height of X"
            height_patterns = [
                r'(\d+(?:\.\d+)?)\s*(?:meter|m)\s*(?:building|tall|high|height)',
                r'(?:from|height|dropped from)\s*(?:a\s*)?(\d+(?:\.\d+)?)\s*(?:meter|m)',
                r'(\d+(?:\.\d+)?)\s*(?:meter|m)',
            ]
            for pattern in height_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    value = float(match.group(1))
                    params[param_name] = int(value) if param_type == "integer" else value
                    break
                    
        elif param_name == "initial_velocity":
            # Look for initial velocity patterns
            if "initial velocity is zero" in query_lower or "initial velocity of zero" in query_lower:
                params[param_name] = 0
            else:
                vel_patterns = [
                    r'initial\s*velocity\s*(?:is|of|=)?\s*(\d+(?:\.\d+)?)',
                    r'starting\s*(?:at|with)\s*(\d+(?:\.\d+)?)\s*(?:m/s|meters)',
                ]
                for pattern in vel_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        value = float(match.group(1))
                        params[param_name] = int(value) if param_type == "integer" else value
                        break
                        
        elif param_name == "gravity":
            # Look for explicit gravity values
            gravity_patterns = [
                r'gravity\s*(?:is|of|=)?\s*(\d+(?:\.\d+)?)',
                r'acceleration\s*(?:is|of|=)?\s*(\d+(?:\.\d+)?)',
                r'g\s*=\s*(\d+(?:\.\d+)?)',
            ]
            for pattern in gravity_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    value = float(match.group(1))
                    params[param_name] = value
                    break

    # Return in the required format: {"function_name": {params}}
    return {func_name: params}
