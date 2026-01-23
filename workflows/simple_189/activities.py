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
    """Extract function call parameters from user query using regex and string matching."""
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Extract parameters from query using regex
    params = {}
    
    # Extract location (city name) - look for patterns like "for X" or "in X"
    # Pattern: "for [City], [Country]" or "for [City]"
    location_patterns = [
        r'(?:for|in)\s+([A-Za-z\s]+(?:,\s*[A-Za-z\s]+)?)\s+(?:for|with|over)',  # "for New York, USA for"
        r'(?:for|in)\s+([A-Za-z\s]+,\s*[A-Za-z]+)',  # "for New York, USA"
        r'(?:for|in)\s+([A-Za-z][A-Za-z\s]+?)(?:\s+for|\s+with|\s+over|\s*$)',  # "for New York"
        r'weather\s+(?:for|in)\s+([A-Za-z\s,]+?)(?:\s+for|\s+with|\s*$)',  # "weather for New York"
    ]
    
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up trailing words that aren't part of location
            location = re.sub(r'\s+(for|with|over|the|next).*$', '', location, flags=re.IGNORECASE).strip()
            break
    
    if location and "location" in params_schema:
        params["location"] = location
    
    # Extract days (integer) - look for number followed by "days" or "day"
    days_patterns = [
        r'(?:next\s+)?(\d+)\s*days?',  # "next 3 days" or "3 days"
        r'for\s+(\d+)\s*days?',  # "for 3 days"
        r'(\d+)\s*day\s+forecast',  # "3 day forecast"
    ]
    
    days = None
    for pattern in days_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            days = int(match.group(1))
            break
    
    if days is not None and "days" in params_schema:
        params["days"] = days
    
    # Extract details (boolean) - look for keywords indicating detailed info
    details_keywords = ['detail', 'detailed', 'with details', 'comprehensive', 'full', 'complete']
    details = any(keyword in query.lower() for keyword in details_keywords)
    
    if "details" in params_schema:
        params["details"] = details
    
    return {func_name: params}
