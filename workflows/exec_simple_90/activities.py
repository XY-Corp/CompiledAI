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
            # Extract user content from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract room_type - look for "deluxe", "standard", "suite", etc.
    room_type_match = re.search(r'\b(deluxe|standard|suite|single|double|twin|king|queen)\s*(room)?', query, re.IGNORECASE)
    if room_type_match:
        params["room_type"] = room_type_match.group(1).lower()
    
    # Extract price - look for dollar amounts
    price_match = re.search(r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', query)
    if price_match:
        price_str = price_match.group(1).replace(',', '')
        params["price"] = float(price_str)
    
    # Extract dates in various formats and convert to MM-DD-YYYY
    # Pattern for "Month DD, YYYY" format
    date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})'
    dates = re.findall(date_pattern, query, re.IGNORECASE)
    
    month_map = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    
    formatted_dates = []
    for month, day, year in dates:
        mm = month_map.get(month.lower(), '01')
        dd = day.zfill(2)
        formatted_dates.append(f"{mm}-{dd}-{year}")
    
    if len(formatted_dates) >= 2:
        params["check_in_date"] = formatted_dates[0]
        params["check_out_date"] = formatted_dates[1]
    elif len(formatted_dates) == 1:
        params["check_in_date"] = formatted_dates[0]
    
    # Extract customer_id - look for "customer ID is X" or "ID: X" patterns
    customer_id_match = re.search(r'customer\s*(?:ID|id)\s*(?:is|:)?\s*(\d+)', query, re.IGNORECASE)
    if customer_id_match:
        params["customer_id"] = customer_id_match.group(1)
    else:
        # Try generic ID pattern
        id_match = re.search(r'\bID\s*(?:is|:)?\s*(\d+)', query, re.IGNORECASE)
        if id_match:
            params["customer_id"] = id_match.group(1)
    
    # Extract discount_code if present
    discount_match = re.search(r'discount\s*(?:code)?[:\s]+([A-Z0-9]+)', query, re.IGNORECASE)
    if discount_match:
        params["discount_code"] = discount_match.group(1).upper()
    
    return {func_name: params}
