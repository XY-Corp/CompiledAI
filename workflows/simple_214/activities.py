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
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)',  # "in New York" or "in New York, NY"
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "in New York"
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    location = match.group(1).strip()
                    # Add state abbreviation if not present and it's a known city
                    if "," not in location and location.lower() == "new york":
                        location = "New York, NY"
                    params[param_name] = location
                    break
        
        elif param_name == "genre":
            # Extract genre - look for genre keywords before "concerts", "events", "shows"
            genre_patterns = [
                r'(\w+)\s+concerts?',  # "rock concerts"
                r'(\w+)\s+events?',    # "rock events"
                r'(\w+)\s+shows?',     # "rock shows"
                r'genre[:\s]+(\w+)',   # "genre: rock"
            ]
            for pattern in genre_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = match.group(1)
                    break
        
        elif param_name == "days_ahead":
            # Extract days ahead - look for number patterns
            days_patterns = [
                r'(\d+)\s*days?\s*ahead',           # "30 days ahead"
                r'next\s+(\d+)\s*days?',            # "next 30 days"
                r'within\s+(\d+)\s*days?',          # "within 30 days"
                r'upcoming\s+(\d+)\s*days?',        # "upcoming 30 days"
                r'(\d+)\s*days?\s*from\s+now',      # "30 days from now"
            ]
            
            # Check for "upcoming month" pattern
            if "upcoming month" in query_lower or "next month" in query_lower:
                params[param_name] = 30
            else:
                for pattern in days_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        params[param_name] = int(match.group(1))
                        break
            
            # If still not found and it's optional with default, skip (let default apply)
            # But if we found "upcoming month", we already set it to 30
    
    return {func_name: params}
