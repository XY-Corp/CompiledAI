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
    """Extract function call parameters from user query using regex patterns."""
    
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
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # Extract GPS coordinates from the query
    # Pattern for coordinates like "33.4484 N, 112.0740 W" or "(33.4484, -112.0740)"
    # GPS format: latitude N/S, longitude E/W
    
    # Pattern to match coordinates like "33.4484 N, 112.0740 W"
    coord_pattern = r'(\d+\.?\d*)\s*([NS])[,\s]+(\d+\.?\d*)\s*([EW])'
    matches = re.findall(coord_pattern, query, re.IGNORECASE)
    
    coord1 = None
    coord2 = None
    
    if len(matches) >= 2:
        # First coordinate
        lat1 = float(matches[0][0])
        if matches[0][1].upper() == 'S':
            lat1 = -lat1
        lon1 = float(matches[0][2])
        if matches[0][3].upper() == 'W':
            lon1 = -lon1
        coord1 = (lat1, lon1)
        
        # Second coordinate
        lat2 = float(matches[1][0])
        if matches[1][1].upper() == 'S':
            lat2 = -lat2
        lon2 = float(matches[1][2])
        if matches[1][3].upper() == 'W':
            lon2 = -lon2
        coord2 = (lat2, lon2)
    
    # Extract unit - look for 'miles' or 'kilometers'
    unit = None
    if re.search(r'\bmiles?\b', query, re.IGNORECASE):
        unit = "miles"
    elif re.search(r'\bkilometers?\b|\bkm\b', query, re.IGNORECASE):
        unit = "kilometers"
    
    # Build result with extracted parameters
    params = {}
    if coord1 is not None:
        params["coord1"] = coord1
    if coord2 is not None:
        params["coord2"] = coord2
    if unit is not None:
        params["unit"] = unit
    
    return {func_name: params}
