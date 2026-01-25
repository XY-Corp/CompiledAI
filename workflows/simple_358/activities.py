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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract dish type - look for common dish keywords
    dish_patterns = [
        r'\b(cookie|cake|bread|muffin|brownie|pie|tart|scone|biscuit|cracker|pancake|waffle)s?\b',
        r'\b(soup|salad|sandwich|pasta|pizza|burger|steak|chicken|fish|salmon|shrimp)s?\b',
        r'\b(smoothie|juice|shake|drink|cocktail|tea|coffee)s?\b',
    ]
    
    dish = None
    for pattern in dish_patterns:
        match = re.search(pattern, query_lower)
        if match:
            dish = match.group(1)
            break
    
    if dish:
        params["dish"] = dish
    
    # Extract dietary requirements
    diet_mapping = {
        "gluten-free": "Gluten Free",
        "gluten free": "Gluten Free",
        "dairy-free": "Dairy Free",
        "dairy free": "Dairy Free",
        "vegan": "Vegan",
        "vegetarian": "Vegetarian",
    }
    
    diet = []
    for keyword, value in diet_mapping.items():
        if keyword in query_lower:
            diet.append(value)
    
    if diet:
        params["diet"] = diet
    
    # Extract time limit - look for patterns like "30 minutes", "less than 30 min", etc.
    time_patterns = [
        r'(?:less than|under|within|in)\s*(\d+)\s*(?:minutes?|mins?)',
        r'(\d+)\s*(?:minutes?|mins?)\s*(?:or less|max|maximum)?',
        r'(?:takes?|prepare|cook)\s*(?:less than|under)?\s*(\d+)\s*(?:minutes?|mins?)',
    ]
    
    time_limit = None
    for pattern in time_patterns:
        match = re.search(pattern, query_lower)
        if match:
            time_limit = int(match.group(1))
            break
    
    if time_limit is not None:
        params["time_limit"] = time_limit
    
    return {func_name: params}
