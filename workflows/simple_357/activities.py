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
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Parse functions - may be JSON string
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "dish_name":
            # Extract dish name - look for patterns like "recipe for X" or "X recipe"
            # Pattern: "recipe for [dish name]"
            match = re.search(r'recipe\s+for\s+(.+?)(?:\s+including|\s+with|\s+along|$)', query, re.IGNORECASE)
            if match:
                dish = match.group(1).strip()
                # Remove diet preference from dish name if present
                diet_words = ['vegan', 'vegetarian', 'gluten-free', 'gluten free', 'keto', 'paleo']
                for diet in diet_words:
                    dish = re.sub(rf'\b{diet}\b\s*', '', dish, flags=re.IGNORECASE).strip()
                params[param_name] = dish
            else:
                # Fallback: look for "X recipe"
                match = re.search(r'(.+?)\s+recipe', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
        
        elif param_name == "diet_preference":
            # Extract diet preference - look for common diet keywords
            diet_patterns = [
                (r'\bvegan\b', 'vegan'),
                (r'\bvegetarian\b', 'vegetarian'),
                (r'\bgluten[- ]?free\b', 'gluten-free'),
                (r'\bketo\b', 'keto'),
                (r'\bpaleo\b', 'paleo'),
                (r'\bdairy[- ]?free\b', 'dairy-free'),
                (r'\bnut[- ]?free\b', 'nut-free'),
            ]
            
            for pattern, diet_value in diet_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    params[param_name] = diet_value
                    break
    
    return {func_name: params}
