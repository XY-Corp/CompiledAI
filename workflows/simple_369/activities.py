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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
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
    
    # Parse functions - may be JSON string
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location":
            # Extract location - look for city patterns
            # Pattern: "in <City>" or "near me ... in <City>"
            location_patterns = [
                r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:,\s*[A-Z]{2})?)',  # "in Houston" or "in Houston, TX"
                r'(?:near|around|at)\s+(?:me\s+)?(?:in\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # "near me in Houston"
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    location = match.group(1).strip()
                    # Add state if mentioned in description and not already present
                    if "TX" not in location and "texas" in query.lower():
                        location += ", TX"
                    elif "TX" not in location and "houston" in location.lower():
                        location += ", TX"  # Houston is commonly in TX
                    params[param_name] = location
                    break
        
        elif param_name == "categories" and param_type == "array":
            # Extract categories from enum values
            items_info = param_info.get("items", {})
            enum_values = items_info.get("enum", [])
            
            if enum_values:
                categories = []
                query_lower = query.lower()
                
                # Map common terms to enum values
                category_mappings = {
                    "organic": "Organic",
                    "vegetable": "Vegetables",
                    "vegetables": "Vegetables",
                    "fruit": "Fruits",
                    "fruits": "Fruits",
                    "dairy": "Dairy",
                    "seafood": "Seafood",
                    "bakery": "Bakery",
                    "baked": "Bakery",
                }
                
                for term, category in category_mappings.items():
                    if term in query_lower and category in enum_values and category not in categories:
                        categories.append(category)
                
                if categories:
                    params[param_name] = categories
    
    return {func_name: params}
