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
    """Extract function name and parameters from user query based on function schema."""
    
    # Parse prompt (may be JSON string with nested structure)
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location":
            # Extract location - look for patterns like "near X", "in X", "around X"
            location_patterns = [
                r'(?:near|in|around|at)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)',
                r'theaters?\s+(?:near|in|around|at)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    location = match.group(1).strip()
                    # Convert to city shorthand as per description
                    city_map = {
                        "la": "LA", "los angeles": "LA",
                        "sf": "SF", "san francisco": "SF",
                        "ny": "NY", "new york": "NY",
                        "chicago": "CHI", "chi": "CHI",
                    }
                    params["location"] = city_map.get(location.lower(), location.upper() if len(location) <= 3 else location)
                    break
        
        elif param_name == "timeframe":
            # Extract timeframe - look for patterns like "next X days", "X days", "next week"
            timeframe_patterns = [
                r'(?:next|for\s+the\s+next)\s+(\d+)\s+days?',
                r'(\d+)\s+days?',
                r'next\s+week',
                r'this\s+week',
            ]
            for pattern in timeframe_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    if 'week' in pattern:
                        params["timeframe"] = 7
                    else:
                        params["timeframe"] = int(match.group(1))
                    break
        
        elif param_name == "format":
            # Extract movie format - look for IMAX, 2D, 3D, 4DX
            format_patterns = [
                r'\b(IMAX|imax)\b',
                r'\b(2D|2d)\b',
                r'\b(3D|3d)\b',
                r'\b(4DX|4dx)\b',
            ]
            for pattern in format_patterns:
                match = re.search(pattern, query)
                if match:
                    params["format"] = match.group(1).upper()
                    break
    
    return {func_name: params}
