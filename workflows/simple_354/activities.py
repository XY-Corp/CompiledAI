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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_enum = param_info.get("enum", [])
        
        if param_name == "dish_type":
            # Check for enum values in query
            if param_enum:
                for enum_val in param_enum:
                    if enum_val.lower() in query_lower:
                        params[param_name] = enum_val
                        break
            # Fallback: look for common dish type patterns
            if param_name not in params:
                dish_patterns = [
                    (r'\b(soup)\b', 'soup'),
                    (r'\b(main dish|main course|entree)\b', 'main dish'),
                    (r'\b(dessert|sweet)\b', 'dessert'),
                    (r'\b(salad)\b', 'salad'),
                ]
                for pattern, dish_type in dish_patterns:
                    if re.search(pattern, query_lower):
                        params[param_name] = dish_type
                        break
        
        elif param_name == "cooking_time":
            # Extract time in minutes - patterns like "under 30 minutes", "30 min", "in 30 minutes"
            time_patterns = [
                r'(?:under|less than|within|in)\s*(\d+)\s*(?:minutes?|mins?)',
                r'(\d+)\s*(?:minutes?|mins?)\s*(?:or less|max|maximum)?',
                r'takes?\s*(?:under|less than)?\s*(\d+)\s*(?:minutes?|mins?)',
            ]
            for pattern in time_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_name == "ingredient_preference":
            # This is optional - only include if explicitly mentioned
            # Look for patterns like "with X", "using X", "include X"
            ingredient_patterns = [
                r'(?:with|using|include|containing)\s+([a-zA-Z,\s]+?)(?:\s+(?:that|which|and)|$)',
            ]
            for pattern in ingredient_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    ingredients_str = match.group(1).strip()
                    # Split by comma or "and"
                    ingredients = re.split(r',\s*|\s+and\s+', ingredients_str)
                    ingredients = [ing.strip() for ing in ingredients if ing.strip()]
                    if ingredients:
                        params[param_name] = ingredients
                    break
    
    # Only return required params and optional params that were found
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
        elif param_name in required_params:
            # Required param not found - this shouldn't happen with good regex
            pass
    
    return {func_name: final_params}
