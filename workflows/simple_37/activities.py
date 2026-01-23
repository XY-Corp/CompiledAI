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
    """Extract function call parameters from natural language query.
    
    Parses the user query and function schema to extract the appropriate
    function name and parameters. Returns format: {"function_name": {params}}
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract start_location - look for "from X" pattern
    start_match = re.search(r'\bfrom\s+([A-Za-z\s]+?)(?:\s+to\b|\s+with\b|$)', query, re.IGNORECASE)
    if start_match:
        params["start_location"] = start_match.group(1).strip()
    
    # Extract end_location - look for "to X" pattern
    end_match = re.search(r'\bto\s+([A-Za-z\s]+?)(?:\s+with\b|\s+stops?\b|\s+via\b|$)', query, re.IGNORECASE)
    if end_match:
        params["end_location"] = end_match.group(1).strip()
    
    # Extract stops - look for "stops at X and Y" or "stops at X, Y" patterns
    stops = []
    
    # Pattern: "stops at X and Y" or "stops at X, Y, and Z"
    stops_match = re.search(r'stops?\s+at\s+(.+?)(?:\.|$)', query, re.IGNORECASE)
    if stops_match:
        stops_text = stops_match.group(1)
        # Split by "and" and commas
        # First replace " and " with comma for uniform splitting
        stops_text = re.sub(r'\s+and\s+', ', ', stops_text, flags=re.IGNORECASE)
        # Split by comma and clean up
        stop_items = [s.strip() for s in stops_text.split(',') if s.strip()]
        stops = stop_items
    
    # Alternative pattern: "via X and Y"
    if not stops:
        via_match = re.search(r'\bvia\s+(.+?)(?:\.|$)', query, re.IGNORECASE)
        if via_match:
            via_text = via_match.group(1)
            via_text = re.sub(r'\s+and\s+', ', ', via_text, flags=re.IGNORECASE)
            stop_items = [s.strip() for s in via_text.split(',') if s.strip()]
            stops = stop_items
    
    # Add stops to params if found
    if stops:
        params["stops"] = stops
    
    return {func_name: params}
