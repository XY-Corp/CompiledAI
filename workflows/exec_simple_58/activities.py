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
    """
    Extract function call parameters from natural language query.
    Returns format: {"function_name": {"param1": val1, ...}}
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

    # Extract parameters based on schema
    params = {}

    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "coordinates" and param_type == "array":
            # Extract latitude and longitude from query
            # Look for patterns like "90.00 latitude and 0.00 longitude" or "latitude X longitude Y"
            
            lat = None
            lon = None
            
            # Pattern 1: "X latitude" and "Y longitude"
            lat_match = re.search(r'(-?\d+\.?\d*)\s*(?:degrees?\s+)?latitude', query, re.IGNORECASE)
            lon_match = re.search(r'(-?\d+\.?\d*)\s*(?:degrees?\s+)?longitude', query, re.IGNORECASE)
            
            if lat_match:
                lat = float(lat_match.group(1))
            if lon_match:
                lon = float(lon_match.group(1))
            
            # Pattern 2: "latitude X" and "longitude Y"
            if lat is None:
                lat_match = re.search(r'latitude\s+(?:of\s+)?(-?\d+\.?\d*)', query, re.IGNORECASE)
                if lat_match:
                    lat = float(lat_match.group(1))
            if lon is None:
                lon_match = re.search(r'longitude\s+(?:of\s+)?(-?\d+\.?\d*)', query, re.IGNORECASE)
                if lon_match:
                    lon = float(lon_match.group(1))
            
            # Pattern 3: "at X latitude and Y longitude" or similar
            if lat is None or lon is None:
                coord_match = re.search(r'at\s+(-?\d+\.?\d*)\s+latitude\s+and\s+(-?\d+\.?\d*)\s+longitude', query, re.IGNORECASE)
                if coord_match:
                    lat = float(coord_match.group(1))
                    lon = float(coord_match.group(2))
            
            # If we found both coordinates, add them as array
            if lat is not None and lon is not None:
                params[param_name] = [lat, lon]
            else:
                # Fallback: extract all decimal numbers and take first two
                numbers = re.findall(r'-?\d+\.?\d*', query)
                if len(numbers) >= 2:
                    params[param_name] = [float(numbers[0]), float(numbers[1])]

    return {func_name: params}
