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
    """Extract function call parameters from user query using regex/parsing."""
    
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract coordinate pairs using regex
    # Pattern for coordinates like (40.7128, -74.0060)
    coord_pattern = r'\((-?\d+\.?\d*),\s*(-?\d+\.?\d*)\)'
    coord_matches = re.findall(coord_pattern, query)
    
    # Extract unit from query
    unit = "degree"  # default
    if "percent" in query.lower():
        unit = "percent"
    elif "ratio" in query.lower():
        unit = "ratio"
    elif "degree" in query.lower():
        unit = "degree"
    
    # Build parameters
    params = {}
    
    if len(coord_matches) >= 2:
        # First coordinate pair -> point1
        params["point1"] = [float(coord_matches[0][0]), float(coord_matches[0][1])]
        # Second coordinate pair -> point2
        params["point2"] = [float(coord_matches[1][0]), float(coord_matches[1][1])]
    
    # Add unit parameter
    params["unit"] = unit
    
    return {func_name: params}
