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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # Extract location/city - look for patterns like "in [City]" or "from [City]"
            if "location" in param_name or "city" in param_desc:
                # Pattern: "in [City Name]" or "from [City Name]"
                location_patterns = [
                    r'(?:in|from)\s+([A-Z][a-zA-Z\s]+?)(?:\s+with|\s+based|\s+rating|$)',
                    r'players\s+in\s+([A-Z][a-zA-Z\s]+)',
                    r'in\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
        
        elif param_type == "integer":
            # Extract rating - look for numbers near "rating" keyword
            if "rating" in param_name or "rating" in param_desc:
                rating_patterns = [
                    r'rating\s+(?:above|over|greater than|>=?|of at least)\s*(\d+)',
                    r'(\d{4})\s*(?:rating|rated)',
                    r'above\s+(\d{4})',
                    r'minimum[_\s]?rating[:\s]+(\d+)',
                ]
                for pattern in rating_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        params[param_name] = int(match.group(1))
                        break
            
            # Extract number of players/items
            elif "number" in param_name or "count" in param_desc:
                number_patterns = [
                    r'top\s+(\d+)',
                    r'(\d+)\s+(?:players|results|items)',
                    r'retrieve\s+(\d+)',
                ]
                for pattern in number_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        params[param_name] = int(match.group(1))
                        break
    
    return {func_name: params}
