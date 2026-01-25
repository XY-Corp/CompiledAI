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
    
    # Extract location - look for city/state patterns
    # Pattern: "in [City]" or "in [City], [State]" or "in [City] [State]"
    location_patterns = [
        r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s*([A-Z]{2})?',  # "in New York, NY" or "in New York"
        r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "in New York"
    ]
    
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, query)
        if match:
            city = match.group(1).strip()
            state = match.group(2) if match.lastindex >= 2 and match.group(2) else None
            
            # Format as "City, State" - infer state if not provided
            if state:
                location = f"{city}, {state}"
            else:
                # Common city to state mappings
                city_state_map = {
                    "New York": "NY",
                    "Los Angeles": "CA",
                    "Chicago": "IL",
                    "Houston": "TX",
                    "Phoenix": "AZ",
                    "San Francisco": "CA",
                    "Seattle": "WA",
                    "Boston": "MA",
                    "Miami": "FL",
                    "Denver": "CO",
                }
                state = city_state_map.get(city, "")
                if state:
                    location = f"{city}, {state}"
                else:
                    location = city
            break
    
    if location and "location" in params_schema:
        params["location"] = location
    
    # Extract operating hours - look for time patterns
    # Patterns: "until 11 PM", "opens until at least 11 PM", "closes at 11", etc.
    time_patterns = [
        r'(?:until|till|closes?\s+at)\s+(?:at\s+least\s+)?(\d{1,2})\s*(?:PM|pm|p\.m\.)?',
        r'(?:open|opens)\s+until\s+(?:at\s+least\s+)?(\d{1,2})\s*(?:PM|pm|p\.m\.)?',
        r'(\d{1,2})\s*(?:PM|pm|p\.m\.)',
    ]
    
    operating_hours = None
    for pattern in time_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            hour = int(match.group(1))
            # Convert to 24-hour format if it's PM time (and not already in 24h format)
            # Hours like 11 PM should become 23
            if hour < 12 and ('pm' in query.lower() or 'PM' in query):
                hour += 12
            elif hour == 12 and ('pm' in query.lower() or 'PM' in query):
                hour = 24  # Midnight represented as 24
            operating_hours = hour
            break
    
    if operating_hours is not None and "operating_hours" in params_schema:
        params["operating_hours"] = operating_hours
    
    return {func_name: params}
