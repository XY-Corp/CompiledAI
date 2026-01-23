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
    
    Uses regex and string matching to extract location names and other parameters
    from the user's natural language query.
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex patterns
    params = {}
    
    # For driving distance queries, extract origin and destination
    # Common patterns: "between X and Y", "from X to Y"
    
    # Pattern 1: "between X and Y"
    between_pattern = r'between\s+([A-Za-z\s\.]+?)\s+and\s+([A-Za-z\s\.]+?)(?:\s*[,\.]|$)'
    match = re.search(between_pattern, query, re.IGNORECASE)
    
    if match:
        origin = match.group(1).strip().rstrip('.')
        destination = match.group(2).strip().rstrip('.')
    else:
        # Pattern 2: "from X to Y"
        from_to_pattern = r'from\s+([A-Za-z\s\.]+?)\s+to\s+([A-Za-z\s\.]+?)(?:\s*[,\.]|$)'
        match = re.search(from_to_pattern, query, re.IGNORECASE)
        
        if match:
            origin = match.group(1).strip().rstrip('.')
            destination = match.group(2).strip().rstrip('.')
        else:
            # Fallback: try to find city names (capitalized words)
            # Look for patterns like "City Name" or "City Name, State"
            city_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z\.]+)*(?:\s+[A-Z]\.?[A-Z]\.?)?)'
            cities = re.findall(city_pattern, query)
            
            if len(cities) >= 2:
                origin = cities[0].strip()
                destination = cities[1].strip()
            else:
                origin = ""
                destination = ""
    
    # Build params based on schema
    if "origin" in params_schema and origin:
        params["origin"] = origin
    
    if "destination" in params_schema and destination:
        params["destination"] = destination
    
    # Check for unit specification (optional)
    if "unit" in params_schema:
        unit_match = re.search(r'\b(km|kilometers?|mi|miles?)\b', query, re.IGNORECASE)
        if unit_match:
            unit_str = unit_match.group(1).lower()
            if unit_str.startswith('mi'):
                params["unit"] = "miles"
            else:
                params["unit"] = "km"
    
    return {func_name: params}
