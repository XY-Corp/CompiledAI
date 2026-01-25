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
    
    query_lower = query.lower()
    params = {}
    
    # Extract 'store' parameter - look for store names
    if "store" in props:
        # Common store patterns
        store_patterns = [
            r'\bfrom\s+(\w+)',
            r'\bat\s+(\w+)',
            r'\bin\s+(\w+)\s+store',
        ]
        store = None
        for pattern in store_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                store = match.group(1)
                break
        
        # Check for known stores directly
        known_stores = ["walmart", "costco", "target", "kroger", "safeway", "whole foods", "trader joe's"]
        for known in known_stores:
            if known in query_lower:
                store = known.title()
                break
        
        if store:
            params["store"] = store
    
    # Extract 'food' parameter - look for food items
    if "food" in props:
        # Pattern: "in a/an [food]" or "of a/an [food]" or just common foods
        food_patterns = [
            r'\b(?:in|of)\s+(?:a|an)\s+(\w+)',
            r'\b(?:in|of)\s+(\w+)',
        ]
        food = None
        
        # Check for common foods directly in query
        common_foods = ["avocado", "apple", "banana", "orange", "chicken", "beef", "salmon", "rice", "bread", "milk", "egg", "eggs"]
        for item in common_foods:
            if item in query_lower:
                food = item
                break
        
        if not food:
            for pattern in food_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    food = match.group(1)
                    break
        
        if food:
            params["food"] = food
    
    # Extract 'information' parameter - look for nutritional info types
    if "information" in props:
        # Get allowed enum values from schema
        enum_values = props["information"].get("items", {}).get("enum", [])
        
        info_list = []
        for enum_val in enum_values:
            # Check if the enum value (or variations) appears in query
            enum_lower = enum_val.lower()
            if enum_lower in query_lower:
                info_list.append(enum_val)
            # Handle plural/singular variations
            elif enum_lower == "calories" and "calorie" in query_lower:
                info_list.append(enum_val)
            elif enum_lower == "carbohydrates" and "carb" in query_lower:
                info_list.append(enum_val)
        
        if info_list:
            params["information"] = info_list
    
    return {func_name: params}
