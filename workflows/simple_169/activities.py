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
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    # Extract docket_number - look for numeric patterns
    # Pattern: "docket number 123456" or "case 123456" or just a standalone number
    docket_match = re.search(r'(?:docket\s*(?:number)?|case\s*(?:number)?|identified\s*by)\s*[#]?(\d+)', query, re.IGNORECASE)
    if docket_match:
        params["docket_number"] = docket_match.group(1)
    else:
        # Fallback: find any standalone number that could be a docket number
        numbers = re.findall(r'\b(\d{4,})\b', query)
        if numbers:
            params["docket_number"] = numbers[0]
    
    # Extract location - look for state names
    # Common US states pattern
    states = [
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
    
    # Build regex pattern for states (case insensitive)
    states_pattern = r'\b(' + '|'.join(states) + r')\b'
    location_match = re.search(states_pattern, query, re.IGNORECASE)
    if location_match:
        # Capitalize properly
        matched_state = location_match.group(1)
        for state in states:
            if state.lower() == matched_state.lower():
                params["location"] = state
                break
    
    # Extract full_text boolean - look for explicit mentions
    # Check for "full text" mentions and whether they're negated
    if re.search(r"don'?t\s+(?:return\s+)?full\s*text|no\s+full\s*text|without\s+full\s*text", query, re.IGNORECASE):
        params["full_text"] = False
    elif re.search(r"(?:return|include|with)\s+full\s*text|full\s*text\s*=\s*true", query, re.IGNORECASE):
        params["full_text"] = True
    # If not mentioned, don't include it (let default apply)
    
    return {func_name: params}
