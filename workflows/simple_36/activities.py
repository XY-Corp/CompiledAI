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
    from natural language queries about driving distances.
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
    
    # Extract parameters using regex patterns for location-based queries
    params = {}
    
    # Pattern for "between X and Y" - common for distance queries
    between_pattern = r'between\s+([A-Za-z\s\.]+?)\s+and\s+([A-Za-z\s\.]+?)(?:\s*[,\.]|$|\s+in\s+|\s+using\s+)'
    between_match = re.search(between_pattern, query, re.IGNORECASE)
    
    # Pattern for "from X to Y"
    from_to_pattern = r'from\s+([A-Za-z\s\.]+?)\s+to\s+([A-Za-z\s\.]+?)(?:\s*[,\.]|$|\s+in\s+|\s+using\s+)'
    from_to_match = re.search(from_to_pattern, query, re.IGNORECASE)
    
    origin = None
    destination = None
    
    if between_match:
        origin = between_match.group(1).strip()
        destination = between_match.group(2).strip()
    elif from_to_match:
        origin = from_to_match.group(1).strip()
        destination = from_to_match.group(2).strip()
    
    # Clean up location names - remove trailing punctuation
    if origin:
        origin = re.sub(r'[,\.\?!]+$', '', origin).strip()
    if destination:
        destination = re.sub(r'[,\.\?!]+$', '', destination).strip()
    
    # Map extracted values to parameter names from schema
    if "origin" in params_schema and origin:
        params["origin"] = origin
    if "destination" in params_schema and destination:
        params["destination"] = destination
    
    # Check for optional unit parameter
    if "unit" in params_schema:
        # Look for unit mentions in query
        unit_patterns = [
            (r'\b(miles?|mi)\b', 'miles'),
            (r'\b(kilometers?|km)\b', 'km'),
            (r'\b(meters?|m)\b', 'm'),
        ]
        for pattern, unit_value in unit_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                params["unit"] = unit_value
                break
    
    return {func_name: params}
