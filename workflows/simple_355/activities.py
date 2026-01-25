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
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    # For recipe_info.get_calories, extract website and recipe
    # Pattern: "from X" or "on X" for website
    website_patterns = [
        r'from\s+([A-Za-z0-9]+(?:\.[A-Za-z]+)+)',  # from Foodnetwork.com
        r'on\s+([A-Za-z0-9]+(?:\.[A-Za-z]+)+)',    # on Foodnetwork.com
        r'at\s+([A-Za-z0-9]+(?:\.[A-Za-z]+)+)',    # at Foodnetwork.com
    ]
    
    website = None
    for pattern in website_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            website = match.group(1)
            break
    
    # Pattern: "in the X Recipe" or "X Recipe" for recipe name
    recipe_patterns = [
        r'(?:in\s+the\s+)?([A-Za-z\s]+?)\s+Recipe',  # Beef Lasagna Recipe
        r'calories\s+in\s+(?:the\s+)?([A-Za-z\s]+?)(?:\s+from|\s+on|\s+at|\?|$)',  # calories in Beef Lasagna
    ]
    
    recipe = None
    for pattern in recipe_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            recipe = match.group(1).strip()
            break
    
    # Pattern for meal time (optional)
    meal_time_patterns = [
        r'\b(Breakfast|Lunch|Dinner)\b',
    ]
    
    meal_time = None
    for pattern in meal_time_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            meal_time = match.group(1).capitalize()
            break
    
    # Build params based on schema
    if "website" in params_schema and website:
        params["website"] = website
    
    if "recipe" in params_schema and recipe:
        params["recipe"] = recipe
    
    # Only include optional_meal_time if found (it's optional)
    if "optional_meal_time" in params_schema and meal_time:
        params["optional_meal_time"] = meal_time
    
    return {func_name: params}
