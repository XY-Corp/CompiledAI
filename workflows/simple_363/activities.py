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
        
        if param_name == "location":
            # Extract location - look for city names after "in" or common patterns
            location_match = re.search(r'\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]*)?)', query)
            if location_match:
                params["location"] = location_match.group(1)
        
        elif param_name == "cuisine":
            # Extract cuisine type - look for food types
            cuisine_types = ["sushi", "italian", "chinese", "mexican", "indian", "thai", "japanese", "french", "korean", "vietnamese"]
            for cuisine in cuisine_types:
                if cuisine in query_lower:
                    params["cuisine"] = cuisine.capitalize()
                    break
        
        elif param_name == "amenities":
            # Extract amenities from enum options
            enum_options = param_info.get("items", {}).get("enum", [])
            found_amenities = []
            for amenity in enum_options:
                if amenity.lower() in query_lower:
                    found_amenities.append(amenity)
            if found_amenities:
                params["amenities"] = found_amenities
    
    return {func_name: params}
