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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex to extract coordinate values (longitude and latitude) from the user's query.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract coordinate values using regex
    # Look for patterns like "longitude 123.45" or "long 123.45" or "longitude: 123.45"
    # Also handle negative numbers like "-67.89"
    
    params = {}
    
    # Pattern for longitude - look for "longitude" followed by a number
    long_patterns = [
        r'longitude\s*[:\s]+(-?\d+\.?\d*)',
        r'long\s*[:\s]+(-?\d+\.?\d*)',
        r'longitude\s+(-?\d+\.?\d*)',
        r'long\s+(-?\d+\.?\d*)',
    ]
    
    # Pattern for latitude - look for "latitude" followed by a number
    lat_patterns = [
        r'latitude\s*[:\s]+(-?\d+\.?\d*)',
        r'lat\s*[:\s]+(-?\d+\.?\d*)',
        r'latitude\s+(-?\d+\.?\d*)',
        r'lat\s+(-?\d+\.?\d*)',
    ]
    
    # Extract longitude
    long_value = None
    for pattern in long_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            long_value = match.group(1)
            break
    
    # Extract latitude
    lat_value = None
    for pattern in lat_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            lat_value = match.group(1)
            break
    
    # If specific patterns didn't work, try to find numbers in context
    # Look for "longitude X and latitude Y" pattern
    if long_value is None or lat_value is None:
        coord_pattern = r'longitude\s+(-?\d+\.?\d*)\s+and\s+latitude\s+(-?\d+\.?\d*)'
        match = re.search(coord_pattern, query, re.IGNORECASE)
        if match:
            long_value = match.group(1)
            lat_value = match.group(2)
    
    # Build params based on function schema
    if "long" in props and long_value is not None:
        params["long"] = long_value
    if "lat" in props and lat_value is not None:
        params["lat"] = lat_value
    
    return {func_name: params}
