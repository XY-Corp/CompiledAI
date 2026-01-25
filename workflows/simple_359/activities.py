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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "dietary_restriction":
            # Extract dietary restriction - look for common patterns
            dietary_patterns = [
                r'\b(vegetarian|vegan|gluten[- ]?free|dairy[- ]?free|keto|paleo|pescatarian)\b'
            ]
            for pattern in dietary_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    # Capitalize properly
                    restriction = match.group(1).replace("-", " ").replace("  ", " ")
                    params[param_name] = restriction.title()
                    break
        
        elif param_name == "ingredients":
            # Extract ingredients - look for food items mentioned
            # Common patterns: "with X", "using X", specific food items
            ingredients = []
            
            # Look for items after "with" or specific food items
            food_items = [
                'pasta', 'cheese', 'tomato', 'tomatoes', 'garlic', 'onion', 'basil',
                'olive oil', 'mushroom', 'mushrooms', 'spinach', 'pepper', 'peppers',
                'zucchini', 'eggplant', 'broccoli', 'chicken', 'beef', 'pork', 'fish',
                'shrimp', 'tofu', 'beans', 'rice', 'bread', 'butter', 'cream', 'milk',
                'egg', 'eggs', 'carrot', 'carrots', 'potato', 'potatoes', 'lettuce',
                'cucumber', 'avocado', 'lemon', 'lime', 'parmesan', 'mozzarella'
            ]
            
            for item in food_items:
                if item in query_lower:
                    # Capitalize and add (avoid duplicates)
                    item_cap = item.title()
                    if item_cap not in ingredients:
                        ingredients.append(item_cap)
            
            params[param_name] = ingredients
        
        elif param_name == "servings":
            # Extract number of servings - look for numbers near "serving" or "people"
            serving_patterns = [
                r'(\d+)\s*(?:servings?|people|persons?|portions?)',
                r'for\s*(\d+)',
                r'serves?\s*(\d+)',
            ]
            
            for pattern in serving_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                    break
            
            # If no match found, try to find any standalone number
            if param_name not in params:
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    # Take the first reasonable number (1-100 range for servings)
                    for num in numbers:
                        n = int(num)
                        if 1 <= n <= 100:
                            params[param_name] = n
                            break
        
        elif param_type == "integer":
            # Generic integer extraction
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # For other string params, try to extract based on description keywords
            # This is a fallback - specific params should be handled above
            pass
    
    return {func_name: params}
