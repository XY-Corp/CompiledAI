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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract topic - look for patterns like "related to X" or "about X"
    topic_patterns = [
        r'related to\s+([a-zA-Z\s]+?)(?:\s+in\s+the|\s+from|\s+in\s+[A-Z]|$)',
        r'about\s+([a-zA-Z\s]+?)(?:\s+in\s+the|\s+from|\s+in\s+[A-Z]|$)',
        r'cases?\s+(?:on|regarding|concerning)\s+([a-zA-Z\s]+?)(?:\s+in\s+the|\s+from|\s+in\s+[A-Z]|$)',
    ]
    
    for pattern in topic_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["topic"] = match.group(1).strip()
            break
    
    if "topic" not in params:
        # Fallback: look for common legal topics
        if "land dispute" in query_lower:
            params["topic"] = "land disputes"
        elif "land" in query_lower:
            params["topic"] = "land disputes"
    
    # Extract year_range - look for year patterns
    year_patterns = [
        r'from\s+(\d{4})\s+to\s+(\d{4})',
        r'between\s+(\d{4})\s+and\s+(\d{4})',
        r'(\d{4})\s*[-–]\s*(\d{4})',
        r'past\s+\d+\s+years?\s+from\s+(\d{4})\s+to\s+(\d{4})',
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            start_year = int(match.group(1))
            end_year = int(match.group(2))
            params["year_range"] = [start_year, end_year]
            break
    
    if "year_range" not in params:
        # Fallback: extract all 4-digit years
        years = re.findall(r'\b(19\d{2}|20\d{2})\b', query)
        if len(years) >= 2:
            years = [int(y) for y in years]
            params["year_range"] = [min(years), max(years)]
    
    # Extract location - look for state/city names
    location_patterns = [
        r'in\s+([A-Z][a-zA-Z\s]+?)(?:\.|$|,|\s+from|\s+in\s+the)',
        r'(?:state|city|county)\s+of\s+([A-Z][a-zA-Z\s]+)',
    ]
    
    # Common US states for matching
    us_states = [
        "New York", "California", "Texas", "Florida", "Illinois", "Pennsylvania",
        "Ohio", "Georgia", "North Carolina", "Michigan", "New Jersey", "Virginia",
        "Washington", "Arizona", "Massachusetts", "Tennessee", "Indiana", "Missouri",
        "Maryland", "Wisconsin", "Colorado", "Minnesota", "South Carolina", "Alabama",
        "Louisiana", "Kentucky", "Oregon", "Oklahoma", "Connecticut", "Utah", "Iowa",
        "Nevada", "Arkansas", "Mississippi", "Kansas", "New Mexico", "Nebraska",
        "West Virginia", "Idaho", "Hawaii", "New Hampshire", "Maine", "Montana",
        "Rhode Island", "Delaware", "South Dakota", "North Dakota", "Alaska",
        "Vermont", "Wyoming"
    ]
    
    for state in us_states:
        if state.lower() in query_lower:
            params["location"] = state
            break
    
    if "location" not in params:
        for pattern in location_patterns:
            match = re.search(pattern, query)
            if match:
                params["location"] = match.group(1).strip().rstrip('.')
                break
    
    # Extract judicial_system - look for federal/state keywords
    if "state law" in query_lower or "state court" in query_lower:
        params["judicial_system"] = "state"
    elif "federal law" in query_lower or "federal court" in query_lower:
        params["judicial_system"] = "federal"
    elif "state" in query_lower and "federal" not in query_lower:
        params["judicial_system"] = "state"
    elif "federal" in query_lower:
        params["judicial_system"] = "federal"
    
    return {func_name: params}
