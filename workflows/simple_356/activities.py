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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "servings":
            # Look for "serves X" or "X people" patterns
            match = re.search(r'serves?\s+(\d+)', query_lower)
            if not match:
                match = re.search(r'(\d+)\s+(?:people|persons|servings)', query_lower)
            if match:
                params[param_name] = int(match.group(1))
        
        elif param_name == "diet":
            # Look for dietary keywords
            diet_keywords = ['vegan', 'vegetarian', 'gluten-free', 'gluten free', 'keto', 'paleo', 'dairy-free', 'dairy free']
            for diet in diet_keywords:
                if diet in query_lower:
                    # Normalize to standard format
                    params[param_name] = diet.replace(' ', '-') if ' ' in diet else diet
                    break
        
        elif param_name == "prep_time":
            # Look for time patterns: "under X minutes", "X minutes", "less than X min"
            match = re.search(r'(?:under|less than|within|max|maximum)?\s*(\d+)\s*(?:minutes?|mins?)', query_lower)
            if match:
                params[param_name] = int(match.group(1))
    
    return {func_name: params}
