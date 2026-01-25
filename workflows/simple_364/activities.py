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
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "location":
            # Extract location - look for "near X", "in X", "around X"
            location_patterns = [
                r'near\s+([A-Za-z\s]+?)(?:\?|$|,|\.|!)',
                r'in\s+([A-Za-z\s]+?)(?:\?|$|,|\.|!)',
                r'around\s+([A-Za-z\s]+?)(?:\?|$|,|\.|!)',
                r'at\s+([A-Za-z\s]+?)(?:\?|$|,|\.|!)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "type":
            # Extract cuisine type - look for common cuisine types
            cuisine_types = [
                "italian", "chinese", "japanese", "mexican", "indian", "thai",
                "french", "korean", "vietnamese", "greek", "american", "spanish",
                "mediterranean", "middle eastern", "brazilian", "ethiopian"
            ]
            for cuisine in cuisine_types:
                if cuisine in query_lower:
                    params[param_name] = cuisine.capitalize()
                    break
        
        elif param_name == "diet_option":
            # Extract dietary preferences
            diet_options = [
                ("gluten-free", "Gluten-free"),
                ("gluten free", "Gluten-free"),
                ("vegan", "Vegan"),
                ("vegetarian", "Vegetarian"),
                ("halal", "Halal"),
                ("kosher", "Kosher"),
                ("dairy-free", "Dairy-free"),
                ("dairy free", "Dairy-free"),
                ("nut-free", "Nut-free"),
                ("nut free", "Nut-free"),
                ("keto", "Keto"),
                ("paleo", "Paleo"),
            ]
            for diet_lower, diet_formatted in diet_options:
                if diet_lower in query_lower:
                    params[param_name] = diet_formatted
                    break
    
    return {func_name: params}
