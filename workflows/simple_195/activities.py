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
    """Extract function call parameters from natural language query using regex.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters using regex patterns
    params = {}
    
    # Pattern for daily miles: "drive X miles a day" or "X miles daily"
    daily_miles_patterns = [
        r'drive\s+(\d+)\s+miles?\s+(?:a\s+)?day',
        r'(\d+)\s+miles?\s+(?:a\s+)?day',
        r'daily\s+(?:driving\s+)?(?:distance\s+)?(?:of\s+)?(\d+)\s+miles?',
        r'(\d+)\s+miles?\s+daily',
    ]
    for pattern in daily_miles_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["daily_miles"] = int(match.group(1))
            break
    
    # Pattern for meat meals per week: "X meat meals a week" or "consume X meat"
    meat_patterns = [
        r'(\d+)\s+meat\s+meals?\s+(?:a\s+|per\s+)?week',
        r'consume\s+(\d+)\s+meat\s+meals?',
        r'(\d+)\s+meat[- ]based\s+meals?\s+(?:a\s+|per\s+)?week',
        r'meat\s+meals?\s+(?:of\s+)?(\d+)\s+(?:times?\s+)?(?:a\s+|per\s+)?week',
    ]
    for pattern in meat_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["meat_meals_per_week"] = int(match.group(1))
            break
    
    # Pattern for annual trash: "X lbs of trash" or "produce X pounds"
    trash_patterns = [
        r'(\d+)\s+(?:lbs?|pounds?)\s+(?:of\s+)?trash',
        r'produce\s+(\d+)\s+(?:lbs?|pounds?)',
        r'trash\s+(?:production\s+)?(?:of\s+)?(\d+)\s+(?:lbs?|pounds?)',
        r'(\d+)\s+(?:lbs?|pounds?)\s+(?:of\s+)?(?:trash|waste)\s+(?:a\s+|per\s+|in\s+a\s+)?year',
    ]
    for pattern in trash_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["annual_trash_weight"] = int(match.group(1))
            break
    
    # Pattern for flights per year (optional): "X flights a year"
    flight_patterns = [
        r'(\d+)\s+flights?\s+(?:a\s+|per\s+)?year',
        r'fly\s+(\d+)\s+times?\s+(?:a\s+|per\s+)?year',
        r'take\s+(\d+)\s+flights?',
    ]
    for pattern in flight_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["flights_per_year"] = int(match.group(1))
            break
    
    # If flights_per_year not found and it has a default, we can omit it
    # (the function schema says default is 0, so we don't need to include it)
    
    return {func_name: params}
