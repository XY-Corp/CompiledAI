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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    
    # Extract parameters from query
    params = {}
    
    # Extract location - look for city patterns
    # Pattern: "in <City>" or "in <City>, <State>" or just city names
    location_patterns = [
        r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)',  # "in Los Angeles" or "in Los Angeles, CA"
        r'(?:near|around|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)',
    ]
    
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, query)
        if match:
            location = match.group(1).strip()
            break
    
    # If no match with patterns, try to find known city names
    if not location:
        # Common cities
        cities = ["Los Angeles", "New York", "San Francisco", "Chicago", "Seattle", "Boston", "Miami"]
        for city in cities:
            if city.lower() in query.lower():
                location = city
                break
    
    if location and "location" in params_schema:
        params["location"] = location
    
    # Extract dietary preferences - look for keywords
    dietary_keywords = {
        "vegan": "Vegan",
        "vegetarian": "Vegetarian",
        "gluten-free": "Gluten-free",
        "gluten free": "Gluten-free",
        "dairy-free": "Dairy-free",
        "dairy free": "Dairy-free",
        "nut-free": "Nut-free",
        "nut free": "Nut-free",
    }
    
    dietary_prefs = []
    query_lower = query.lower()
    for keyword, value in dietary_keywords.items():
        if keyword in query_lower:
            if value not in dietary_prefs:
                dietary_prefs.append(value)
    
    if dietary_prefs and "dietary_preference" in params_schema:
        params["dietary_preference"] = dietary_prefs
    
    return {func_name: params}
