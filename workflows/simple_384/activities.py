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
    
    Parses the user query and extracts parameters to match the function schema.
    Returns format: {"function_name": {"param1": val1, ...}}
    """
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Extract city - look for "in [City]" pattern
    city_match = re.search(r'\bin\s+([A-Za-z\s]+?)(?:,|\s+from|\s+on|\s+for|\s+starting|$)', query, re.IGNORECASE)
    if city_match:
        city_raw = city_match.group(1).strip()
        # Handle "Paris, France" format - take just the city or full location
        if "city" in props:
            # Check if there's a country after comma
            full_location_match = re.search(r'\bin\s+([A-Za-z\s]+,\s*[A-Za-z\s]+?)(?:\s+from|\s+on|\s+for|\s+starting|$)', query, re.IGNORECASE)
            if full_location_match:
                params["city"] = full_location_match.group(1).strip()
            else:
                params["city"] = city_raw
    
    # Extract dates - look for date patterns
    # Pattern for "Month DD, YYYY" or "Month DD YYYY"
    date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})'
    dates = re.findall(date_pattern, query, re.IGNORECASE)
    
    month_map = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    
    if len(dates) >= 2:
        # First date is from_date, second is to_date
        month1, day1, year1 = dates[0]
        month2, day2, year2 = dates[1]
        
        mm1 = month_map.get(month1.lower(), '01')
        mm2 = month_map.get(month2.lower(), '01')
        
        # Format as MM-DD-YYYY
        if "from_date" in props:
            params["from_date"] = f"{mm1}-{int(day1):02d}-{year1}"
        if "to_date" in props:
            params["to_date"] = f"{mm2}-{int(day2):02d}-{year2}"
    
    # Extract numbers for adults and children
    # Look for patterns like "two adults", "2 adults", "one child", "1 child"
    word_to_num = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    
    # Extract adults
    adults_match = re.search(r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+adults?', query, re.IGNORECASE)
    if adults_match and "adults" in props:
        val = adults_match.group(1).lower()
        params["adults"] = word_to_num.get(val, int(val) if val.isdigit() else 1)
    
    # Extract children
    children_match = re.search(r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+child(?:ren)?', query, re.IGNORECASE)
    if children_match and "children" in props:
        val = children_match.group(1).lower()
        params["children"] = word_to_num.get(val, int(val) if val.isdigit() else 0)
    
    # Extract room_type if mentioned (optional parameter)
    room_types = ['Standard', 'Deluxe', 'Suite']
    for room_type in room_types:
        if room_type.lower() in query.lower():
            if "room_type" in props:
                params["room_type"] = room_type
            break
    
    return {func_name: params}
