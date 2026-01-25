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
    
    Uses regex and string parsing to extract values - no LLM calls needed.
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # Extract location - look for patterns like "at the X" or "in X"
            if "location" in param_name.lower() or "location" in param_desc:
                # Pattern: "at the [Store Name] in [City]" or "in [City]"
                location_match = re.search(
                    r'(?:at\s+(?:the\s+)?)?(?:Whole\s+Foods\s+)?(?:in|at)\s+([A-Za-z\s]+?)(?:\.|$|,|\s+(?:for|to|and))',
                    query,
                    re.IGNORECASE
                )
                if location_match:
                    params[param_name] = location_match.group(1).strip()
                else:
                    # Fallback: look for city names after "in"
                    city_match = re.search(r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', query)
                    if city_match:
                        params[param_name] = city_match.group(1).strip()
        
        elif param_type == "array":
            # Extract items - look for lists of things
            if "items" in param_name.lower() or "item" in param_desc:
                # Pattern: "price of X and Y" or "price of X, Y, and Z"
                items_match = re.search(
                    r'(?:price\s+of|check|for)\s+([a-zA-Z\s,]+?)(?:\s+at|\s+in|\.|$)',
                    query,
                    re.IGNORECASE
                )
                if items_match:
                    items_str = items_match.group(1).strip()
                    # Split by "and" and commas
                    items_str = re.sub(r'\s+and\s+', ', ', items_str, flags=re.IGNORECASE)
                    items = [item.strip() for item in items_str.split(',') if item.strip()]
                    params[param_name] = items
    
    return {func_name: params}
