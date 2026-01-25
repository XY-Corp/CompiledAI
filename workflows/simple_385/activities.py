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
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract location - look for city patterns
    # Pattern: "in [City]" or "[City], [State]"
    location_patterns = [
        r'in\s+([A-Z][a-zA-Z\s]+?)(?:\s+for|\s+starting|\s+from|,|\.|$)',
        r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?),?\s*(?:CA|NY|TX|FL|WA|IL|PA|OH|GA|NC|MI|NJ|VA|AZ|MA|TN|IN|MO|MD|WI|CO|MN|SC|AL|LA|KY|OR|OK|CT|UT|IA|NV|AR|MS|KS|NM|NE|WV|ID|HI|NH|ME|MT|RI|DE|SD|ND|AK|VT|WY|DC)?',
    ]
    
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, query)
        if match:
            loc = match.group(1).strip()
            if len(loc) > 2:  # Avoid single letters
                location = loc
                # Check if state abbreviation follows
                state_match = re.search(rf'{re.escape(loc)},?\s*(CA|NY|TX|FL|WA|IL|PA|OH|GA|NC|MI|NJ|VA|AZ|MA|TN|IN|MO|MD|WI|CO|MN|SC|AL|LA|KY|OR|OK|CT|UT|IA|NV|AR|MS|KS|NM|NE|WV|ID|HI|NH|ME|MT|RI|DE|SD|ND|AK|VT|WY|DC)', query)
                if state_match:
                    location = f"{loc}, {state_match.group(1)}"
                break
    
    if location and "location" in props:
        params["location"] = location
    
    # Extract room type - look for bed/room type keywords
    room_type_patterns = [
        r'(king\s*size|queen\s*size|deluxe|suite|standard|single|double|twin)\s*(?:bed|room)?',
        r'(king|queen)\s+(?:size\s+)?bed',
    ]
    
    room_type = None
    for pattern in room_type_patterns:
        match = re.search(pattern, query_lower)
        if match:
            room_type = match.group(1).strip()
            break
    
    if room_type and "room_type" in props:
        params["room_type"] = room_type
    
    # Extract check-in date - look for date patterns
    date_patterns = [
        # "15th October, 2023" or "15th October 2023"
        r'(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December),?\s*(\d{4})',
        # "October 15, 2023" or "October 15th, 2023"
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})',
        # "15-10-2023" or "15/10/2023"
        r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})',
    ]
    
    month_map = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    
    check_in_date = None
    for i, pattern in enumerate(date_patterns):
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            if i == 0:  # "15th October, 2023"
                day = match.group(1).zfill(2)
                month = month_map.get(match.group(2).lower(), '01')
                year = match.group(3)
                check_in_date = f"{day}-{month}-{year}"
            elif i == 1:  # "October 15, 2023"
                month = month_map.get(match.group(1).lower(), '01')
                day = match.group(2).zfill(2)
                year = match.group(3)
                check_in_date = f"{day}-{month}-{year}"
            elif i == 2:  # "15-10-2023"
                day = match.group(1).zfill(2)
                month = match.group(2).zfill(2)
                year = match.group(3)
                check_in_date = f"{day}-{month}-{year}"
            break
    
    if check_in_date and "check_in_date" in props:
        params["check_in_date"] = check_in_date
    
    # Extract number of nights
    nights_patterns = [
        r'(\d+)\s*nights?',
        r'for\s+(\d+)\s*nights?',
    ]
    
    no_of_nights = None
    for pattern in nights_patterns:
        match = re.search(pattern, query_lower)
        if match:
            no_of_nights = int(match.group(1))
            break
    
    if no_of_nights and "no_of_nights" in props:
        params["no_of_nights"] = no_of_nights
    
    # Extract number of rooms (optional, default is 1)
    rooms_patterns = [
        r'(\d+)\s*rooms?',
        r'book\s+(\d+)\s*rooms?',
    ]
    
    no_of_rooms = None
    for pattern in rooms_patterns:
        match = re.search(pattern, query_lower)
        if match:
            no_of_rooms = int(match.group(1))
            break
    
    if no_of_rooms and "no_of_rooms" in props:
        params["no_of_rooms"] = no_of_rooms
    
    return {func_name: params}
