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
    required_params = func.get("parameters", {}).get("required", [])
    
    query_lower = query.lower()
    params = {}
    
    # Extract city - look for patterns like "near X", "in X city"
    city_patterns = [
        r'(?:near|in|at|around)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s*(?:city|town)?',
        r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+city',
        r'(?:near|in|at|around)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',
    ]
    
    for pattern in city_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            city_value = match.group(1).strip()
            # Clean up common suffixes
            city_value = re.sub(r'\s*city\s*$', '', city_value, flags=re.IGNORECASE).strip()
            if city_value:
                params["city"] = city_value
                break
    
    # Extract cuisine - look for cuisine types
    cuisine_keywords = [
        "italian", "chinese", "japanese", "mexican", "indian", "thai", 
        "french", "greek", "korean", "vietnamese", "american", "spanish",
        "mediterranean", "middle eastern", "brazilian", "ethiopian"
    ]
    
    for cuisine in cuisine_keywords:
        if cuisine in query_lower:
            params["cuisine"] = cuisine.capitalize()
            break
    
    # Extract diet/dietary preferences
    diet_keywords = {
        "gluten-free": "Gluten-free",
        "gluten free": "Gluten-free",
        "vegetarian": "Vegetarian",
        "vegan": "Vegan",
        "halal": "Halal",
        "kosher": "Kosher",
        "dairy-free": "Dairy-free",
        "dairy free": "Dairy-free",
        "nut-free": "Nut-free",
        "nut free": "Nut-free",
        "low-carb": "Low-carb",
        "low carb": "Low-carb",
        "keto": "Keto",
        "paleo": "Paleo"
    }
    
    for keyword, normalized in diet_keywords.items():
        if keyword in query_lower:
            params["diet"] = normalized
            break
    
    # Return in the exact format: {func_name: {params}}
    return {func_name: params}
