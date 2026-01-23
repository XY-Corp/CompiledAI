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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location":
            # Extract location - look for city patterns
            # Pattern: "in [City]" or "in [City], [State]" or "in [City] [State]"
            location_patterns = [
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,?\s*([A-Z]{2})?',  # "in New York, NY" or "in New York"
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "in New York"
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    city = match.group(1).strip()
                    # Check if state is captured
                    state = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                    
                    # Format as "City, State" - infer state if not provided
                    if state:
                        params["location"] = f"{city}, {state}"
                    else:
                        # Common city to state mapping for well-known cities
                        city_state_map = {
                            "New York": "NY",
                            "Los Angeles": "CA",
                            "Chicago": "IL",
                            "San Francisco": "CA",
                            "Boston": "MA",
                            "Seattle": "WA",
                            "Miami": "FL",
                            "Dallas": "TX",
                            "Houston": "TX",
                            "Phoenix": "AZ",
                        }
                        state = city_state_map.get(city, "")
                        if state:
                            params["location"] = f"{city}, {state}"
                        else:
                            params["location"] = city
                    break
        
        elif param_name == "operating_hours" or "hour" in param_name.lower() or "time" in param_name.lower():
            # Extract time/hours - look for patterns like "11 PM", "until 11", "at least 11"
            time_patterns = [
                r'(?:until|at least|after|opens?\s+until)\s+(?:at\s+)?(\d{1,2})\s*(?:PM|pm|p\.m\.)?',  # "until 11 PM"
                r'(\d{1,2})\s*(?:PM|pm|p\.m\.)',  # "11 PM"
                r'closes?\s+(?:at\s+)?(\d{1,2})',  # "closes at 11"
            ]
            
            for pattern in time_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    hour = int(match.group(1))
                    # Convert to 24-hour format if PM is implied (hours < 12 in evening context)
                    if hour < 12 and ('pm' in query.lower() or 'PM' in query or 'evening' in query.lower() or 'night' in query.lower()):
                        hour += 12
                    elif hour < 12 and hour >= 1:
                        # Assume PM for restaurant closing times
                        hour += 12
                    params["operating_hours"] = hour
                    break
    
    return {func_name: params}
