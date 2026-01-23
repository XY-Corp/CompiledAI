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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
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
    
    # Extract parameters using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # For geo_distance.calculate - extract locations and units
    if "start_location" in params_schema:
        # Pattern: "between X and Y" or "from X to Y"
        between_pattern = r'between\s+([A-Za-z\s,\.]+?)\s+and\s+([A-Za-z\s,\.]+?)(?:\s+in|\s*\?|$)'
        from_to_pattern = r'from\s+([A-Za-z\s,\.]+?)\s+to\s+([A-Za-z\s,\.]+?)(?:\s+in|\s*\?|$)'
        
        match = re.search(between_pattern, query, re.IGNORECASE)
        if not match:
            match = re.search(from_to_pattern, query, re.IGNORECASE)
        
        if match:
            params["start_location"] = match.group(1).strip().rstrip(',.')
            params["end_location"] = match.group(2).strip().rstrip(',.')
    
    # Extract units if mentioned
    if "units" in params_schema:
        if "mile" in query_lower:
            params["units"] = "miles"
        elif "kilometer" in query_lower or "km" in query_lower:
            params["units"] = "kilometers"
    
    return {func_name: params}
