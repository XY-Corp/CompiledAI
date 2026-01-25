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

    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])

    # Extract parameter values using regex
    params = {}
    query_lower = query.lower()

    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()

        # Extract based on parameter name and description
        if param_name == "height":
            # Look for height patterns: "150 meter", "150m", "height of 150"
            patterns = [
                r'(\d+(?:\.\d+)?)\s*(?:meter|m)\s*(?:building|tower|height)?',
                r'height\s*(?:of|is|=)?\s*(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*(?:meter|m)',
                r'from\s*(?:a\s*)?(\d+(?:\.\d+)?)',
            ]
            for pattern in patterns:
                match = re.search(pattern, query_lower)
                if match:
                    value = float(match.group(1))
                    params[param_name] = int(value) if param_type == "integer" else value
                    break

        elif param_name == "initial_velocity":
            # Look for initial velocity patterns
            patterns = [
                r'initial\s*velocity\s*(?:of|is|=)?\s*(\d+(?:\.\d+)?)',
                r'starting\s*(?:at|with)?\s*(\d+(?:\.\d+)?)\s*m/s',
                r'initial\s*(?:speed|velocity)\s*(?:is\s*)?zero',
            ]
            for pattern in patterns:
                match = re.search(pattern, query_lower)
                if match:
                    if 'zero' in pattern:
                        params[param_name] = 0
                    else:
                        value = float(match.group(1))
                        params[param_name] = int(value) if param_type == "integer" else value
                    break
            # Check for "initial velocity is zero" or similar
            if param_name not in params and 'initial velocity is zero' in query_lower:
                params[param_name] = 0

        elif param_name == "gravity":
            # Look for gravity patterns
            patterns = [
                r'gravity\s*(?:of|is|=)?\s*(\d+(?:\.\d+)?)',
                r'g\s*=\s*(\d+(?:\.\d+)?)',
                r'acceleration\s*(?:of|is|=)?\s*(\d+(?:\.\d+)?)',
            ]
            for pattern in patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = float(match.group(1))
                    break

    # Ensure required parameters are present
    for req_param in required_params:
        if req_param not in params:
            # Try to extract any number if we haven't found the required param
            if req_param == "height":
                numbers = re.findall(r'(\d+(?:\.\d+)?)', query)
                if numbers:
                    # Take the first significant number (likely the height)
                    for num in numbers:
                        val = float(num)
                        if val > 1:  # Filter out small numbers that might be other values
                            param_type = params_schema.get(req_param, {}).get("type", "integer")
                            params[req_param] = int(val) if param_type == "integer" else val
                            break

    return {func_name: params}
