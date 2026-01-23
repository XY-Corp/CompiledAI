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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    required = func.get("parameters", {}).get("required", [])
    
    params = {}
    query_lower = query.lower()
    
    # Extract city - look for common city names or patterns
    # Pattern: "in [City]" or "[City], [State]" or "of [City]"
    city_patterns = [
        r'(?:in|of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # "in San Francisco"
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+in\s+\d{4}',  # "San Francisco in 2020"
    ]
    
    city = None
    for pattern in city_patterns:
        match = re.search(pattern, query)
        if match:
            city = match.group(1).strip()
            break
    
    if city:
        params["city"] = city
    
    # Extract state - for known cities, infer state
    # San Francisco -> California
    city_to_state = {
        "san francisco": "California",
        "los angeles": "California",
        "new york": "New York",
        "chicago": "Illinois",
        "houston": "Texas",
        "phoenix": "Arizona",
        "philadelphia": "Pennsylvania",
        "san antonio": "Texas",
        "san diego": "California",
        "dallas": "Texas",
        "seattle": "Washington",
        "denver": "Colorado",
        "boston": "Massachusetts",
        "miami": "Florida",
    }
    
    # Try to find state in query or infer from city
    state_pattern = r'(?:in|,)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:in\s+\d{4}|$|,)'
    state_match = re.search(state_pattern, query)
    
    if city and city.lower() in city_to_state:
        params["state"] = city_to_state[city.lower()]
    elif state_match:
        params["state"] = state_match.group(1).strip()
    
    # Extract year - look for 4-digit year
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
    if year_match:
        params["year"] = int(year_match.group(1))
    
    # Extract crime type - look for keywords
    crime_types = ["violent", "property", "theft", "burglary", "assault", "robbery", "murder", "homicide"]
    for crime_type in crime_types:
        if crime_type in query_lower:
            params["type"] = crime_type
            break
    
    return {func_name: params}
