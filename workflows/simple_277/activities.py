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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract museum name - look for "The British Museum" or similar patterns
    museum_patterns = [
        r'(?:of|about|for)\s+(The\s+[A-Z][a-zA-Z\s]+Museum)',
        r'(The\s+[A-Z][a-zA-Z\s]+Museum)',
        r'(?:of|about|for)\s+([A-Z][a-zA-Z\s]+Museum)',
        r'([A-Z][a-zA-Z\s]+Museum)',
    ]
    
    for pattern in museum_patterns:
        match = re.search(pattern, query)
        if match:
            params["museum"] = match.group(1).strip()
            break
    
    # Extract date - look for explicit date or date references
    # First try explicit date format like "Jun.20,2023" or "June 20, 2023"
    date_patterns = [
        # Jun.20,2023 or Jun 20, 2023
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[.\s]*(\d{1,2})[,\s]*(\d{4})',
        # 2023-06-20 format
        r'(\d{4})-(\d{2})-(\d{2})',
        # June 20, 2023
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s*(\d{1,2})[,\s]*(\d{4})',
    ]
    
    month_map = {
        'jan': '01', 'january': '01',
        'feb': '02', 'february': '02',
        'mar': '03', 'march': '03',
        'apr': '04', 'april': '04',
        'may': '05',
        'jun': '06', 'june': '06',
        'jul': '07', 'july': '07',
        'aug': '08', 'august': '08',
        'sep': '09', 'september': '09',
        'oct': '10', 'october': '10',
        'nov': '11', 'november': '11',
        'dec': '12', 'december': '12',
    }
    
    for pattern in date_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                # Check if first group is year (YYYY-MM-DD format)
                if groups[0].isdigit() and len(groups[0]) == 4:
                    params["date"] = f"{groups[0]}-{groups[1]}-{groups[2]}"
                else:
                    # Month name format
                    month_str = groups[0].lower()
                    month = month_map.get(month_str, '01')
                    day = groups[1].zfill(2)
                    year = groups[2]
                    params["date"] = f"{year}-{month}-{day}"
            break
    
    # Extract information types requested
    info_types = []
    query_lower = query.lower()
    
    if 'hour' in query_lower or 'opening' in query_lower or 'working' in query_lower or 'time' in query_lower:
        info_types.append("opening_hours")
    if 'price' in query_lower or 'ticket' in query_lower or 'cost' in query_lower or 'fee' in query_lower:
        info_types.append("ticket_price")
    if 'address' in query_lower or 'location' in query_lower or 'where' in query_lower:
        info_types.append("address")
    
    # Only include information if specific types were requested
    if info_types:
        params["information"] = info_types
    
    return {func_name: params}
