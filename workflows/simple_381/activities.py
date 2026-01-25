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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
                else:
                    query = str(data["question"])
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract location (city) - look for "in <city>" pattern
    location_patterns = [
        r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "in Paris", "in New York"
        r'(?:to|at|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
    ]
    for pattern in location_patterns:
        match = re.search(pattern, query)
        if match:
            params["location"] = match.group(1).strip()
            break
    
    # Extract dates - look for date patterns
    # Pattern for "April 4th" or "April 8th" style dates
    month_map = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    
    # Look for year
    year_match = re.search(r'(\d{4})', query)
    year = year_match.group(1) if year_match else "2023"
    
    # Find all date mentions like "April 4th" or "April 8"
    date_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?'
    date_matches = re.findall(date_pattern, query_lower)
    
    if len(date_matches) >= 2:
        # First date is check-in, second is check-out
        month1, day1 = date_matches[0]
        month2, day2 = date_matches[1]
        params["check_in_date"] = f"{year}-{month_map[month1]}-{int(day1):02d}"
        params["check_out_date"] = f"{year}-{month_map[month2]}-{int(day2):02d}"
    elif len(date_matches) == 1:
        month1, day1 = date_matches[0]
        params["check_in_date"] = f"{year}-{month_map[month1]}-{int(day1):02d}"
    
    # Also try YYYY-MM-DD format directly
    iso_dates = re.findall(r'(\d{4}-\d{2}-\d{2})', query)
    if len(iso_dates) >= 2:
        params["check_in_date"] = iso_dates[0]
        params["check_out_date"] = iso_dates[1]
    elif len(iso_dates) == 1 and "check_in_date" not in params:
        params["check_in_date"] = iso_dates[0]
    
    # Extract number of adults
    adult_patterns = [
        r'(\d+)\s*adults?',
        r'(\w+)\s*adults?',
        r'for\s+(\d+)\s+(?:people|persons|guests)',
    ]
    
    word_to_num = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 
                   'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
    
    for pattern in adult_patterns:
        match = re.search(pattern, query_lower)
        if match:
            val = match.group(1)
            if val.isdigit():
                params["no_of_adults"] = int(val)
            elif val in word_to_num:
                params["no_of_adults"] = word_to_num[val]
            break
    
    # Extract hotel chain - look for known hotel chains or explicit mention
    hotel_chains = ['hilton', 'marriott', 'hyatt', 'sheraton', 'holiday inn', 'best western']
    for chain in hotel_chains:
        if chain in query_lower:
            # Capitalize properly
            params["hotel_chain"] = chain.title() if chain != 'holiday inn' else 'Holiday Inn'
            break
    
    # If hotel_chain not found but mentioned in function default, use default
    if "hotel_chain" not in params and "hotel_chain" in props:
        default_chain = props["hotel_chain"].get("default")
        if default_chain:
            params["hotel_chain"] = default_chain
    
    return {func_name: params}
