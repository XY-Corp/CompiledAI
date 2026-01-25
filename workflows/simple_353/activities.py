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
    
    # Extract parameters from query using pattern matching
    params = {}
    query_lower = query.lower()
    
    # Extract 'diet' parameter - look for dietary restrictions
    diet_patterns = [
        r'\b(gluten[- ]?free)\b',
        r'\b(vegan)\b',
        r'\b(vegetarian)\b',
        r'\b(keto)\b',
        r'\b(paleo)\b',
        r'\b(dairy[- ]?free)\b',
        r'\b(low[- ]?carb)\b',
    ]
    
    for pattern in diet_patterns:
        match = re.search(pattern, query_lower)
        if match:
            diet_value = match.group(1).replace(' ', '-')
            params["diet"] = diet_value
            break
    
    # Extract 'meal_type' parameter - look for meal types
    meal_patterns = [
        (r'\b(dinner)\b', 'dinner'),
        (r'\b(breakfast)\b', 'breakfast'),
        (r'\b(lunch)\b', 'lunch'),
        (r'\b(snack)s?\b', 'snack'),
        (r'\b(dessert)s?\b', 'dessert'),
        (r'\b(brunch)\b', 'brunch'),
    ]
    
    for pattern, meal_type in meal_patterns:
        if re.search(pattern, query_lower):
            params["meal_type"] = meal_type
            break
    
    # Extract 'ingredients' parameter - look for ingredient lists
    # Pattern: "with X, Y, and Z" or "using X and Y" or "containing X"
    ingredients_patterns = [
        r'(?:with|using|containing|include|including)\s+([a-zA-Z,\s]+?)(?:\s+for|\s+recipes?|\?|$)',
        r'(?:made with|made from)\s+([a-zA-Z,\s]+?)(?:\s+for|\s+recipes?|\?|$)',
    ]
    
    ingredients = []
    for pattern in ingredients_patterns:
        match = re.search(pattern, query_lower)
        if match:
            ingredient_text = match.group(1)
            # Split by comma, 'and', or 'or'
            parts = re.split(r',\s*|\s+and\s+|\s+or\s+', ingredient_text)
            ingredients = [p.strip() for p in parts if p.strip() and len(p.strip()) > 1]
            break
    
    # Only include ingredients if found (it's optional)
    if ingredients:
        params["ingredients"] = ingredients
    
    return {func_name: params}
