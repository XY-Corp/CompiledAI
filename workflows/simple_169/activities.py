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
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Parse functions - may be JSON string
    if isinstance(functions, str):
        try:
            funcs = json.loads(functions)
        except json.JSONDecodeError:
            funcs = []
    else:
        funcs = functions if functions else []
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    
    # Extract docket_number - look for numeric patterns
    # Pattern: "docket number 123456" or "case 123456" or just a standalone number
    docket_patterns = [
        r'docket\s*(?:number|#|no\.?)?\s*(\d+)',
        r'case\s*(?:number|#|no\.?)?\s*(\d+)',
        r'identified\s+by\s+(?:docket\s+number\s+)?(\d+)',
    ]
    
    docket_number = None
    for pattern in docket_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            docket_number = match.group(1)
            break
    
    # Fallback: find any standalone number that looks like a docket number
    if not docket_number:
        numbers = re.findall(r'\b(\d{4,})\b', query)
        if numbers:
            docket_number = numbers[0]
    
    if docket_number and "docket_number" in params_schema:
        params["docket_number"] = docket_number
    
    # Extract location - look for state names
    # Common patterns: "in Texas", "in California", "located in New York"
    location_patterns = [
        r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',
        r'located\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'registered\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
    ]
    
    # List of US states for validation
    us_states = [
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
        "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
        "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
        "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
        "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
        "New Hampshire", "New Jersey", "New Mexico", "New York",
        "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
        "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
        "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
        "West Virginia", "Wisconsin", "Wyoming"
    ]
    
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, query)
        if match:
            potential_location = match.group(1)
            # Validate it's a state
            if potential_location in us_states:
                location = potential_location
                break
    
    # Fallback: search for any state name in the query
    if not location:
        for state in us_states:
            if state.lower() in query.lower():
                location = state
                break
    
    if location and "location" in params_schema:
        params["location"] = location
    
    # Extract full_text boolean - look for explicit mentions
    if "full_text" in params_schema:
        # Check for negative indicators (don't return full text)
        negative_patterns = [
            r"don'?t\s+(?:return|include|show|get)\s+full\s*text",
            r"no\s+full\s*text",
            r"without\s+full\s*text",
            r"exclude\s+full\s*text",
        ]
        
        # Check for positive indicators
        positive_patterns = [
            r"(?:return|include|show|get|with)\s+full\s*text",
            r"full\s*text\s*=\s*true",
        ]
        
        full_text = None
        
        for pattern in negative_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                full_text = False
                break
        
        if full_text is None:
            for pattern in positive_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    full_text = True
                    break
        
        # Only include if explicitly mentioned
        if full_text is not None:
            params["full_text"] = full_text
    
    return {func_name: params}
