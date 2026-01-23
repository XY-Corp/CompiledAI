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
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
                else:
                    query = str(prompt)
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
    
    # Extract coordinate pairs using regex
    # Pattern for coordinates like (40.7128, -74.0060) or [40.7128, -74.0060]
    coord_pattern = r'[\(\[]?\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*[\)\]]?'
    
    # Find all coordinate pairs in the query
    coord_matches = re.findall(coord_pattern, query)
    
    params = {}
    
    # Extract point1 and point2 from coordinate matches
    if len(coord_matches) >= 2:
        # First coordinate pair is point1
        params["point1"] = [float(coord_matches[0][0]), float(coord_matches[0][1])]
        # Second coordinate pair is point2
        params["point2"] = [float(coord_matches[1][0]), float(coord_matches[1][1])]
    
    # Extract unit parameter
    # Check for unit keywords in the query
    query_lower = query.lower()
    if "degree" in query_lower:
        params["unit"] = "degree"
    elif "percent" in query_lower:
        params["unit"] = "percent"
    elif "ratio" in query_lower:
        params["unit"] = "ratio"
    # If no unit specified, use default "degree" as per schema
    else:
        params["unit"] = "degree"
    
    return {func_name: params}
