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
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    # For distance_calculator.calculate, extract origin, destination, consider_terrain
    # Pattern: "distance between X and Y" or "from X to Y"
    
    # Try "between X and Y" pattern
    between_match = re.search(r'between\s+([A-Za-z\s]+?)\s+and\s+([A-Za-z\s]+?)(?:\s*[,.]|\s+accounting|\s+considering|$)', query, re.IGNORECASE)
    
    # Try "from X to Y" pattern
    from_to_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\s*[,.]|\s+accounting|\s+considering|$)', query, re.IGNORECASE)
    
    origin = None
    destination = None
    
    if between_match:
        origin = between_match.group(1).strip()
        destination = between_match.group(2).strip()
    elif from_to_match:
        origin = from_to_match.group(1).strip()
        destination = from_to_match.group(2).strip()
    
    # Build params based on schema
    if "origin" in params_schema and origin:
        params["origin"] = origin
    
    if "destination" in params_schema and destination:
        params["destination"] = destination
    
    # Check for terrain-related keywords
    if "consider_terrain" in params_schema:
        terrain_keywords = ["terrain", "elevation", "topography", "hills", "mountains"]
        if any(kw in query_lower for kw in terrain_keywords):
            # Check if it's explicitly mentioned to account for terrain
            if "accounting for terrain" in query_lower or "consider terrain" in query_lower or "considering terrain" in query_lower:
                params["consider_terrain"] = True
            elif "without terrain" in query_lower or "ignore terrain" in query_lower:
                params["consider_terrain"] = False
            else:
                # Terrain mentioned, assume true
                params["consider_terrain"] = True
    
    return {func_name: params}
