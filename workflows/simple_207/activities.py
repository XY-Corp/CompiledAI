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
    
    Uses regex and string matching to extract location parameters from the query.
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
    
    # For distance/route queries, extract locations
    # Pattern: "between X and Y" or "from X to Y"
    between_pattern = r'between\s+([A-Za-z,\s]+?)\s+and\s+([A-Za-z,\s]+?)(?:\.|$)'
    from_to_pattern = r'from\s+([A-Za-z,\s]+?)\s+to\s+([A-Za-z,\s]+?)(?:\.|$)'
    
    start_location = None
    end_location = None
    
    # Try "between X and Y" pattern
    match = re.search(between_pattern, query, re.IGNORECASE)
    if match:
        start_location = match.group(1).strip()
        end_location = match.group(2).strip()
    else:
        # Try "from X to Y" pattern
        match = re.search(from_to_pattern, query, re.IGNORECASE)
        if match:
            start_location = match.group(1).strip()
            end_location = match.group(2).strip()
    
    # Assign extracted values to parameters based on schema
    if "start_location" in params_schema and start_location:
        params["start_location"] = start_location
    
    if "end_location" in params_schema and end_location:
        params["end_location"] = end_location
    
    # Extract route preference - check for keywords in query
    if "route_preference" in params_schema:
        query_lower = query.lower()
        if "scenic" in query_lower:
            params["route_preference"] = "Scenic"
        elif "shortest" in query_lower or "short" in query_lower:
            params["route_preference"] = "Shortest"
        else:
            # Default to "Shortest" for driving distance queries
            params["route_preference"] = "Shortest"
    
    return {func_name: params}
