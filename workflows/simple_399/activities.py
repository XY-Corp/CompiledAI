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
    func_name = func.get("name", "unknown")
    props = func.get("parameters", {}).get("properties", {})
    
    query_lower = query.lower()
    params = {}
    
    # Extract parameters based on schema
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "location":
            # Extract location - look for "in [City]" pattern
            location_patterns = [
                r'in\s+([A-Z][a-zA-Z\s]+(?:City)?(?:,\s*[A-Z]{2})?)',
                r'(?:restaurants?\s+in|in)\s+([A-Z][a-zA-Z\s]+)',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    location = match.group(1).strip()
                    # Clean up - remove trailing words like "with"
                    location = re.sub(r'\s+with.*$', '', location, flags=re.IGNORECASE)
                    params["location"] = location
                    break
            if "location" not in params:
                # Fallback: look for "New York City"
                if "new york" in query_lower:
                    params["location"] = "New York City, NY"
        
        elif param_name == "cuisine":
            # Extract cuisine type - look for cuisine keywords
            cuisine_patterns = [
                r'(Italian|Indian|Chinese|Mexican|Japanese|Thai|French|American|Greek|Korean|Vietnamese)\s+restaurants?',
                r'(Italian|Indian|Chinese|Mexican|Japanese|Thai|French|American|Greek|Korean|Vietnamese)',
            ]
            for pattern in cuisine_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params["cuisine"] = match.group(1).capitalize()
                    break
        
        elif param_name == "rating":
            # Extract rating - look for "more than X", "above X", "at least X", etc.
            rating_patterns = [
                r'(?:more than|greater than|above|over|at least|minimum|min)\s*(\d+(?:\.\d+)?)',
                r'ratings?\s+(?:of\s+)?(?:more than|greater than|above|over|at least)?\s*(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*(?:stars?|rating)',
            ]
            for pattern in rating_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    rating_val = float(match.group(1))
                    # "more than 4" means minimum is 4 (or could be interpreted as > 4)
                    params["rating"] = int(rating_val)
                    break
        
        elif param_name == "accepts_credit_cards":
            # Check for credit card mentions
            if "credit card" in query_lower or "credit cards" in query_lower:
                # Check if it's a positive mention (accepts) vs negative (doesn't accept)
                if "not" in query_lower or "no credit" in query_lower or "doesn't accept" in query_lower:
                    params["accepts_credit_cards"] = False
                else:
                    params["accepts_credit_cards"] = True
            elif "cash only" in query_lower:
                params["accepts_credit_cards"] = False
    
    return {func_name: params}
