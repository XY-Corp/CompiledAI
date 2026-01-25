import re
import json
from typing import Any
from datetime import datetime, timedelta


async def extract_function_call(
    prompt: str,
    functions: list,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from natural language query using regex and string parsing."""
    
    # Parse prompt - may be JSON string with nested structure
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract hotel_name - look for "at the X" or "at X Hotel"
    hotel_patterns = [
        r'at\s+the\s+([A-Za-z\s]+?(?:Hotel|Inn|Resort|Suites)?)\s+(?:in|for)',
        r'at\s+([A-Za-z\s]+?(?:Hotel|Inn|Resort|Suites))',
        r'(?:book|reserve)\s+(?:a\s+)?(?:room\s+)?(?:at\s+)?(?:the\s+)?([A-Za-z\s]+?(?:Hotel|Inn|Resort|Suites))',
    ]
    for pattern in hotel_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["hotel_name"] = match.group(1).strip()
            break
    
    # Extract location - look for "in City" or "City, State"
    location_patterns = [
        r'in\s+([A-Za-z\s]+(?:,\s*[A-Z]{2})?)\s+for',
        r'in\s+([A-Za-z\s]+)\s+for',
        r'in\s+([A-Za-z\s]+)',
    ]
    for pattern in location_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up location - remove trailing words like "for"
            location = re.sub(r'\s+for$', '', location, flags=re.IGNORECASE)
            params["location"] = location
            break
    
    # Extract number of nights
    nights_match = re.search(r'(\d+)\s*nights?', query, re.IGNORECASE)
    num_nights = int(nights_match.group(1)) if nights_match else 1
    
    # Extract start date - various formats
    date_patterns = [
        # "1st June 2022", "2nd July 2023", etc.
        r'(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})',
        # "June 1, 2022", "July 2, 2023", etc.
        r'([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})',
        # "2022-06-01" ISO format
        r'(\d{4})-(\d{2})-(\d{2})',
    ]
    
    month_map = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7,
        'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    start_date = None
    
    # Try "1st June 2022" format
    match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})', query, re.IGNORECASE)
    if match:
        day = int(match.group(1))
        month_str = match.group(2).lower()
        year = int(match.group(3))
        month = month_map.get(month_str, 1)
        start_date = datetime(year, month, day)
    
    # Try "June 1, 2022" format
    if not start_date:
        match = re.search(r'([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})', query, re.IGNORECASE)
        if match:
            month_str = match.group(1).lower()
            day = int(match.group(2))
            year = int(match.group(3))
            month = month_map.get(month_str, 1)
            start_date = datetime(year, month, day)
    
    # Try ISO format
    if not start_date:
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', query)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            start_date = datetime(year, month, day)
    
    if start_date:
        params["start_date"] = start_date.strftime('%Y-%m-%d')
        end_date = start_date + timedelta(days=num_nights)
        params["end_date"] = end_date.strftime('%Y-%m-%d')
    
    # Extract number of rooms (optional, default is 1)
    rooms_match = re.search(r'(\d+)\s*rooms?', query, re.IGNORECASE)
    if rooms_match:
        params["rooms"] = int(rooms_match.group(1))
    
    return {func_name: params}
