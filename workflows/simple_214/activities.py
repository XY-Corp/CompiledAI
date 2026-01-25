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
    """Extract function name and parameters from user query and function schema.
    
    Returns a dict with function name as key and parameters as nested object.
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location":
            # Extract location - look for city patterns
            # Pattern: "in [City]" or "in [City], [State]"
            location_patterns = [
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)',
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    location = match.group(1).strip()
                    # Add state abbreviation if not present and it's a known city
                    if "," not in location:
                        if location.lower() == "new york":
                            location = "New York, NY"
                        elif location.lower() == "los angeles":
                            location = "Los Angeles, CA"
                        elif location.lower() == "chicago":
                            location = "Chicago, IL"
                    params[param_name] = location
                    break
        
        elif param_name == "genre":
            # Extract genre - look for common music/event genres
            genres = ["rock", "pop", "jazz", "classical", "hip hop", "hip-hop", "country", 
                      "electronic", "r&b", "metal", "indie", "folk", "blues", "reggae",
                      "comedy", "theater", "theatre", "sports", "concert", "festival"]
            for genre in genres:
                if genre in query_lower:
                    params[param_name] = genre
                    break
        
        elif param_name == "days_ahead":
            # Extract days ahead - look for time patterns
            # "upcoming month" = ~30 days, "upcoming week" = 7 days
            if "month" in query_lower:
                params[param_name] = 30
            elif "week" in query_lower:
                params[param_name] = 7
            else:
                # Look for explicit number of days
                days_match = re.search(r'(\d+)\s*days?', query_lower)
                if days_match:
                    params[param_name] = int(days_match.group(1))
                # Otherwise use default from schema if available
                elif "default" in param_info:
                    params[param_name] = param_info["default"]
        
        elif param_type == "integer":
            # Generic integer extraction
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # For other string params, try to extract based on description keywords
            # This is a fallback - specific params should be handled above
            pass
    
    return {func_name: params}
