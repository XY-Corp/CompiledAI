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
        r'cases?\s+(?:on|regarding|concerning)\s+([a-zA-Z\s]+?)(?:\s+in|\s+from|$)',
    ]
    
    topic = None
    for pattern in topic_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            topic = match.group(1).strip()
            break
    
    if topic:
        params["topic"] = topic
    
    # Extract year_range - look for year patterns
    year_patterns = [
        r'from\s+(\d{4})\s+to\s+(\d{4})',
        r'between\s+(\d{4})\s+and\s+(\d{4})',
        r'(\d{4})\s*[-–]\s*(\d{4})',
        r'past\s+\d+\s+years?\s+from\s+(\d{4})\s+to\s+(\d{4})',
    ]
    
    year_range = None
    for pattern in year_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            year_range = [int(match.group(1)), int(match.group(2))]
            break
    
    if year_range:
        params["year_range"] = year_range
    
    # Extract location - look for "in [Location]" patterns (city/state names)
    location_patterns = [
        r'in\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s*[.,]?\s*$',
        r'in\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s*(?:from|between|during)',
        r'(?:heard\s+)?in\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)(?:\s+court)?',
    ]
    
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, query)
        if match:
            loc = match.group(1).strip()
            # Filter out common non-location words
            if loc.lower() not in ['the', 'past', 'last', 'next', 'this']:
                location = loc
                break
    
    if location:
        params["location"] = location
    
    # Extract judicial_system - look for federal/state keywords
    if 'federal' in query_lower:
        params["judicial_system"] = "federal"
    elif 'state law' in query_lower or 'state court' in query_lower or 'state case' in query_lower:
        params["judicial_system"] = "state"
    elif 'state' in query_lower:
        # Check if "state" appears as judicial system context
        state_match = re.search(r'\bstate\s+(law|court|case)', query_lower)
        if state_match:
            params["judicial_system"] = "state"
    
    return {func_name: params}
