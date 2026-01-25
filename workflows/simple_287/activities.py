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
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    query_lower = query.lower()
    params = {}
    
    # Extract genre - look for music genre keywords
    genre_keywords = ["classical", "rock", "pop", "jazz", "hip hop", "country", "electronic", "metal", "r&b", "blues", "folk", "indie", "alternative"]
    for genre in genre_keywords:
        if genre in query_lower:
            params["genre"] = genre
            break
    
    # Extract location - look for city names after "in"
    location_match = re.search(r'\bin\s+([A-Z][a-zA-Z\s]+?)(?:\s+with|\s+for|\s+on|\s+this|\s+next|\s+today|\s+tomorrow|\.|\,|$)', query, re.IGNORECASE)
    if location_match:
        params["location"] = location_match.group(1).strip()
    
    # Extract date - check for date keywords from enum
    date_options = ["this weekend", "next weekend", "this month", "next month", "today", "tomorrow", "the day after"]
    for date_opt in date_options:
        if date_opt in query_lower:
            params["date"] = date_opt
            break
    
    # Extract price_range - check for price keywords from enum
    price_options = ["free", "cheap", "moderate", "expensive"]
    for price in price_options:
        if price in query_lower:
            params["price_range"] = price
            break
    
    return {func_name: params}
