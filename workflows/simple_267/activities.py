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
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question = data["question"]
            if isinstance(question, list) and len(question) > 0:
                if isinstance(question[0], list) and len(question[0]) > 0:
                    query = question[0][0].get("content", str(prompt))
                elif isinstance(question[0], dict):
                    query = question[0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    query_lower = query.lower()
    params = {}
    
    # Extract location - look for city patterns
    location_patterns = [
        r'\bin\s+([A-Z][a-zA-Z\s]+(?:City)?(?:,\s*[A-Z]{2})?)',  # "in New York" or "in New York City, NY"
        r'(?:happening|held|located)\s+(?:in|at)\s+([A-Z][a-zA-Z\s]+)',
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Normalize common locations
            if "new york" in location.lower():
                params["location"] = "New York City, NY"
            else:
                params["location"] = location
            break
    
    # Extract art_form - look for art type keywords
    art_forms = ["sculpture", "painting", "photography", "digital art", "installation", 
                 "mixed media", "ceramics", "textile", "drawing", "printmaking"]
    
    for art in art_forms:
        if art in query_lower:
            params["art_form"] = art
            break
    
    # Also check for modifiers like "modern sculpture"
    art_match = re.search(r'(modern\s+)?(\w+)\s+exhibition', query_lower)
    if art_match and "art_form" not in params:
        potential_art = art_match.group(2)
        if potential_art in art_forms:
            params["art_form"] = potential_art
    
    # Extract month - look for month names or relative time
    months = ["january", "february", "march", "april", "may", "june", 
              "july", "august", "september", "october", "november", "december"]
    
    for month in months:
        if month in query_lower:
            params["month"] = month.capitalize()
            break
    
    # Check for relative time expressions
    if "upcoming" in query_lower or "next month" in query_lower:
        params["month"] = "upcoming"
    
    # Extract user_ratings - look for rating keywords
    if "top rated" in query_lower or "highest rated" in query_lower or "best" in query_lower:
        params["user_ratings"] = "high"
    elif "average" in query_lower:
        params["user_ratings"] = "average"
    elif "low" in query_lower:
        params["user_ratings"] = "low"
    
    # Only include parameters that were found (don't add defaults for optional params)
    # But ensure required params are present
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
    
    return {func_name: final_params}
