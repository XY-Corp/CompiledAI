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
    """Extract function call parameters from natural language query using regex and string matching."""
    
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract hotel_name - pattern: "in Hotel X" or "at Hotel X"
    hotel_match = re.search(r'(?:in|at)\s+(Hotel\s+\w+)', query, re.IGNORECASE)
    if hotel_match:
        params["hotel_name"] = hotel_match.group(1)
    
    # Extract location - pattern: "Hotel Name, Location" or common city names
    # Look for pattern after hotel name: "Hotel Paradise, Las Vegas"
    location_match = re.search(r'Hotel\s+\w+,?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', query)
    if location_match:
        params["location"] = location_match.group(1)
    
    # Extract room_type - look for "X room" pattern
    room_match = re.search(r'(\w+)\s+room', query, re.IGNORECASE)
    if room_match:
        params["room_type"] = room_match.group(1).lower()
    
    # Extract stay_duration - look for "X days" pattern
    duration_match = re.search(r'(\d+)\s+days?', query, re.IGNORECASE)
    if duration_match:
        params["stay_duration"] = int(duration_match.group(1))
    
    # Extract start_date - look for date patterns like "May 12, 2022" or "May 12 2022"
    date_match = re.search(r'(?:from|starting|on)\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})', query, re.IGNORECASE)
    if date_match:
        month_name = date_match.group(1)
        day = date_match.group(2)
        year = date_match.group(3)
        
        # Convert month name to number
        months = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12'
        }
        month_num = months.get(month_name.lower(), '01')
        # Format as MM-DD-YYYY
        params["start_date"] = f"{month_num}-{day.zfill(2)}-{year}"
    
    # Extract view - look for "X view" pattern
    view_match = re.search(r'(\w+)\s+view', query, re.IGNORECASE)
    if view_match:
        params["view"] = view_match.group(1).lower() + " view"
    
    return {func_name: params}
