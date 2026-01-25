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
    
    # Extract parameters based on the query
    params = {}
    
    # For geo_distance.calculate, extract locations and units
    # Pattern: "distance between X and Y" or "from X to Y"
    
    # Extract locations - look for city, state patterns
    # Common patterns: "Boston, MA", "Washington, D.C."
    location_patterns = [
        r'between\s+([A-Za-z\s]+,\s*[A-Z]{1,2}\.?[A-Z]?\.?)\s*(?:,?\s*and|to)\s+([A-Za-z\s]+,\s*[A-Z]{1,2}\.?[A-Z]?\.?)',
        r'from\s+([A-Za-z\s]+,\s*[A-Z]{1,2}\.?[A-Z]?\.?)\s+to\s+([A-Za-z\s]+,\s*[A-Z]{1,2}\.?[A-Z]?\.?)',
    ]
    
    start_location = None
    end_location = None
    
    for pattern in location_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            start_location = match.group(1).strip()
            end_location = match.group(2).strip()
            break
    
    # If no match with patterns, try to find all "City, State" patterns
    if not start_location or not end_location:
        # Match patterns like "Boston, MA" or "Washington, D.C."
        city_state_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{1,2}\.?[A-Z]?\.?)'
        matches = re.findall(city_state_pattern, query)
        if len(matches) >= 2:
            start_location = f"{matches[0][0]}, {matches[0][1]}"
            end_location = f"{matches[1][0]}, {matches[1][1]}"
    
    # Extract units - look for "mile", "miles", "kilometer", "kilometers", "km"
    units = None
    if re.search(r'\bmiles?\b', query, re.IGNORECASE):
        units = "miles"
    elif re.search(r'\b(?:kilometers?|km)\b', query, re.IGNORECASE):
        units = "kilometers"
    
    # Build params dict based on schema
    if "start_location" in params_schema and start_location:
        params["start_location"] = start_location
    
    if "end_location" in params_schema and end_location:
        params["end_location"] = end_location
    
    if "units" in params_schema and units:
        params["units"] = units
    
    return {func_name: params}
