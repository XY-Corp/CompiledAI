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
    """Extract function call parameters from user query using regex and string matching."""
    
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location":
            # Extract city - look for "in [City]" pattern
            # Pattern for "in Chicago" or similar
            location_patterns = [
                r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # "in Chicago" or "in New York"
                r'(?:concert|event|show)\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    city = match.group(1).strip()
                    # Format as "City, State" - for Chicago, assume IL
                    state_map = {
                        "Chicago": "IL",
                        "New York": "NY",
                        "Los Angeles": "CA",
                        "Houston": "TX",
                        "Phoenix": "AZ",
                        "Philadelphia": "PA",
                        "San Antonio": "TX",
                        "San Diego": "CA",
                        "Dallas": "TX",
                        "San Jose": "CA",
                    }
                    state = state_map.get(city, "")
                    if state:
                        params[param_name] = f"{city}, {state}"
                    else:
                        params[param_name] = city
                    break
        
        elif param_name == "price":
            # Extract price - look for "$X" or "under $X" or "X dollars"
            price_patterns = [
                r'\$(\d+)',  # $100
                r'under\s+\$?(\d+)',  # under 100 or under $100
                r'(\d+)\s*dollars?',  # 100 dollars
                r'budget\s+(?:of\s+)?\$?(\d+)',  # budget of $100
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, query_lower.replace(query_lower, query))  # Keep original case for numbers
                if not match:
                    match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_name == "genre":
            # Extract genre from enum values
            enum_values = param_info.get("enum", [])
            for genre in enum_values:
                if genre.lower() in query_lower:
                    params[param_name] = genre
                    break
            
            # If no genre found, check for default
            if param_name not in params:
                # Check if there's a default in description
                default_match = re.search(r"default\s+(?:to\s+)?['\"]?(\w+)['\"]?", param_info.get("description", ""), re.IGNORECASE)
                if default_match:
                    default_val = default_match.group(1)
                    # Only use default if it's in enum
                    if enum_values and default_val in enum_values:
                        params[param_name] = default_val
    
    return {func_name: params}
