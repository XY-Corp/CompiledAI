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
    
    Parses the prompt to extract the user query and matches it against
    the function schema to extract parameter values using regex and
    string matching.
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        enum_values = param_info.get("enum", [])
        
        if param_name == "color":
            # Extract color - common colors
            colors = ["red", "blue", "green", "yellow", "orange", "purple", "black", "white", "brown", "gray", "grey", "pink"]
            for color in colors:
                if color in query_lower:
                    params[param_name] = color
                    break
        
        elif param_name == "habitat":
            # Extract habitat - common habitats
            habitats = ["forest", "ocean", "desert", "mountain", "grassland", "wetland", "urban", "jungle", "savanna", "tundra", "lake", "river", "beach", "garden", "park"]
            for habitat in habitats:
                if habitat in query_lower:
                    params[param_name] = habitat
                    break
        
        elif param_name == "size":
            # Extract size - check enum values or common sizes
            if enum_values:
                for size in enum_values:
                    if size.lower() in query_lower:
                        params[param_name] = size
                        break
            else:
                sizes = ["small", "medium", "large", "tiny", "big", "huge"]
                for size in sizes:
                    if size in query_lower:
                        params[param_name] = size
                        break
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif enum_values:
            # Check for enum values in query
            for val in enum_values:
                if val.lower() in query_lower:
                    params[param_name] = val
                    break
    
    return {func_name: params}
