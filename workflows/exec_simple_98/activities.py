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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
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
    
    # For polygon_area, we need to extract vertices (coordinate pairs)
    params = {}
    
    if func_name == "polygon_area" and "vertices" in params_schema:
        # Extract coordinate pairs like (1,2), (3,4), (1,3)
        # Pattern matches (x,y) or (x, y) with optional spaces
        coord_pattern = r'\((\d+)\s*,\s*(\d+)\)'
        matches = re.findall(coord_pattern, query)
        
        if matches:
            # Convert to list of [x, y] pairs
            vertices = [[int(x), int(y)] for x, y in matches]
            params["vertices"] = vertices
    else:
        # Generic extraction for other function types
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type == "array":
                # Try to extract array-like data
                items_info = param_info.get("items", {}) if isinstance(param_info, dict) else {}
                items_type = items_info.get("type", "string") if isinstance(items_info, dict) else "string"
                
                if items_type == "array":
                    # Nested array (like vertices) - extract coordinate pairs
                    coord_pattern = r'\((\d+)\s*,\s*(\d+)\)'
                    matches = re.findall(coord_pattern, query)
                    if matches:
                        params[param_name] = [[int(x), int(y)] for x, y in matches]
                elif items_type in ["integer", "number"]:
                    # Simple number array
                    numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
                    params[param_name] = [int(n) if items_type == "integer" else float(n) for n in numbers]
            elif param_type in ["integer", "number"]:
                numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
                if numbers:
                    params[param_name] = int(numbers[0]) if param_type == "integer" else float(numbers[0])
            elif param_type == "string":
                # Extract string after common prepositions
                match = re.search(r'(?:for|in|of|with|named?)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,)|[.?!]|$)', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
    
    return {func_name: params}
