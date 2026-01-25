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
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract location (city name) - look for patterns like "for X" or city names
    if "location" in props:
        # Pattern: "for [City], [Country]" or "for [City]"
        location_match = re.search(r'for\s+([A-Za-z\s]+(?:,\s*[A-Za-z\s]+)?)', query, re.IGNORECASE)
        if location_match:
            location = location_match.group(1).strip()
            # Clean up - remove trailing words like "for the next"
            location = re.sub(r'\s+for\s+the\s+next.*$', '', location, flags=re.IGNORECASE)
            params["location"] = location
    
    # Extract days (number) - look for "X days" or "next X days"
    if "days" in props:
        days_match = re.search(r'(?:next\s+)?(\d+)\s*days?', query, re.IGNORECASE)
        if days_match:
            params["days"] = int(days_match.group(1))
    
    # Extract details (array of weather details)
    if "details" in props:
        details = []
        query_lower = query.lower()
        
        # Check for high/low temperatures
        if any(term in query_lower for term in ["high", "low", "temperature", "temperatures"]):
            details.append("high_low_temperature")
        
        # Check for humidity
        if "humidity" in query_lower:
            details.append("humidity")
        
        # Check for precipitation
        if "precipitation" in query_lower:
            details.append("precipitation")
        
        if details:
            params["details"] = details
    
    return {func_name: params}
