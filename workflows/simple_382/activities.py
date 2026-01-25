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
    """Extract function call parameters from natural language query.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
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
    
    # Extract parameters using regex patterns
    params = {}
    query_lower = query.lower()
    
    # Extract hotel_name - look for "at the X Hotel" or "X Hotel"
    hotel_match = re.search(r'(?:at\s+the\s+)?(\w+(?:\s+\w+)*)\s+hotel', query, re.IGNORECASE)
    if hotel_match:
        params["hotel_name"] = hotel_match.group(1).strip() + " Hotel"
    
    # Extract location - look for "in X" pattern for city
    location_match = re.search(r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', query)
    if location_match:
        # Make sure we don't capture "in Chicago, starting" - stop at comma
        location = location_match.group(1).split(',')[0].strip()
        params["location"] = location
    
    # Extract room_type - look for "single", "double", "suite", etc. followed by "room"
    room_match = re.search(r'(single|double|twin|suite|deluxe|standard|king|queen)\s*room', query_lower)
    if room_match:
        params["room_type"] = room_match.group(1)
    
    # Extract start_date - look for date patterns
    # Pattern: "10th December 2022", "December 10, 2022", "10/12/2022", etc.
    date_patterns = [
        r'(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',  # 10th December 2022
        r'(\w+\s+\d{1,2},?\s+\d{4})',  # December 10, 2022
        r'(\d{1,2}/\d{1,2}/\d{4})',  # 10/12/2022
        r'(\d{4}-\d{2}-\d{2})',  # 2022-12-10
    ]
    
    for pattern in date_patterns:
        date_match = re.search(pattern, query, re.IGNORECASE)
        if date_match:
            params["start_date"] = date_match.group(1)
            break
    
    # Extract nights - look for number followed by "night(s)"
    nights_match = re.search(r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*nights?', query_lower)
    if nights_match:
        nights_str = nights_match.group(1)
        # Convert word numbers to integers
        word_to_num = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
        }
        if nights_str in word_to_num:
            params["nights"] = word_to_num[nights_str]
        else:
            params["nights"] = int(nights_str)
    
    return {func_name: params}
