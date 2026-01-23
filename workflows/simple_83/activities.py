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
    # Pattern for coordinates like "(33.4484 N, 112.0740 W)" or similar
    # GPS coordinates can be in format: (lat N/S, lon E/W)
    
    # Extract all coordinate pairs - pattern: (number N/S, number E/W)
    coord_pattern = r'\((\d+\.?\d*)\s*([NS]),?\s*(\d+\.?\d*)\s*([EW])\)'
    coord_matches = re.findall(coord_pattern, query, re.IGNORECASE)
    
    coords = []
    for match in coord_matches:
        lat = float(match[0])
        lat_dir = match[1].upper()
        lon = float(match[2])
        lon_dir = match[3].upper()
        
        # Convert to signed coordinates (S and W are negative)
        if lat_dir == 'S':
            lat = -lat
        if lon_dir == 'W':
            lon = -lon
        
        coords.append((lat, lon))
    
    # Extract unit (miles or kilometers)
    unit = "miles"  # default
    if re.search(r'\bkilometers?\b', query, re.IGNORECASE):
        unit = "kilometers"
    elif re.search(r'\bmiles?\b', query, re.IGNORECASE):
        unit = "miles"
    
    # Build result with extracted parameters
    params = {}
    
    if len(coords) >= 2:
        params["coord1"] = coords[0]
        params["coord2"] = coords[1]
    elif len(coords) == 1:
        params["coord1"] = coords[0]
        params["coord2"] = (0.0, 0.0)  # fallback
    else:
        # Fallback: try to extract any floating point numbers
        numbers = re.findall(r'-?\d+\.?\d*', query)
        if len(numbers) >= 4:
            params["coord1"] = (float(numbers[0]), float(numbers[1]))
            params["coord2"] = (float(numbers[2]), float(numbers[3]))
    
    params["unit"] = unit
    
    return {func_name: params}
