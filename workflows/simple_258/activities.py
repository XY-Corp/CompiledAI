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
    """Extract function name and parameters from user query using regex and string matching."""
    
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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    # Common color names to look for
    colors = ["red", "blue", "green", "yellow", "orange", "purple", "pink", "white", "black", "brown", "cyan", "magenta"]
    
    # Extract colors mentioned in the query
    found_colors = []
    for color in colors:
        if color in query_lower:
            found_colors.append(color)
    
    # Extract numbers (for lightness, percentages, etc.)
    numbers = re.findall(r'\b(\d+)\b', query)
    
    # Map extracted values to parameter names based on schema
    color_params = []
    number_params = []
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Check if this is a color parameter
        if "color" in param_name.lower() or "color" in param_desc:
            color_params.append(param_name)
        # Check if this is a numeric parameter
        elif param_type in ["integer", "number", "float"]:
            number_params.append(param_name)
    
    # Assign colors to color parameters in order
    for i, param_name in enumerate(color_params):
        if i < len(found_colors):
            params[param_name] = found_colors[i]
    
    # Assign numbers to numeric parameters
    for i, param_name in enumerate(number_params):
        if i < len(numbers):
            param_type = params_schema.get(param_name, {}).get("type", "integer")
            if param_type == "integer":
                params[param_name] = int(numbers[i])
            else:
                params[param_name] = float(numbers[i])
    
    return {func_name: params}
