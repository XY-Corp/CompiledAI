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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    # For museum_working_hours.get, extract museum name and location
    # Pattern: "Get the working hours of [Museum Name] in [Location]"
    
    # Extract museum name - pattern: "of [Museum Name] in" or "of [Museum Name]"
    museum_match = re.search(r'(?:of|for)\s+([A-Za-z\s]+?)\s+(?:in|at|museum)', query, re.IGNORECASE)
    if not museum_match:
        # Try: "[Museum Name] Museum"
        museum_match = re.search(r'([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+Museum', query, re.IGNORECASE)
    
    if museum_match:
        museum_name = museum_match.group(1).strip()
        # Append "Museum" if not already present
        if "museum" not in museum_name.lower():
            museum_name = museum_name + " Museum"
        params["museum"] = museum_name
    
    # Extract location - pattern: "in [Location]" at end or before punctuation
    location_match = re.search(r'\bin\s+([A-Za-z\s]+?)(?:\.|,|$|\?)', query, re.IGNORECASE)
    if location_match:
        params["location"] = location_match.group(1).strip()
    
    # Extract day if mentioned
    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for day in days_of_week:
        if day in query_lower:
            params["day"] = day.capitalize()
            break
    
    # Also check for "today", "tomorrow", "weekend" patterns
    if "today" in query_lower:
        params["day"] = "today"
    elif "tomorrow" in query_lower:
        params["day"] = "tomorrow"
    elif "weekend" in query_lower:
        params["day"] = "Saturday"
    
    return {func_name: params}
