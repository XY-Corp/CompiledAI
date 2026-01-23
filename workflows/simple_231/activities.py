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
    """Extract function name and parameters from user query using regex and string matching."""
    
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    
    # Extract country - look for country names
    # Common patterns: "in German history", "for Germany", "German", etc.
    country_patterns = [
        r'\b(German|Germany)\b',
        r'\b(French|France)\b',
        r'\b(British|Britain|UK|United Kingdom|England)\b',
        r'\b(American|America|USA|United States)\b',
        r'\b(Italian|Italy)\b',
        r'\b(Spanish|Spain)\b',
        r'\b(Russian|Russia)\b',
        r'\b(Chinese|China)\b',
        r'\b(Japanese|Japan)\b',
    ]
    
    country_map = {
        'German': 'Germany', 'Germany': 'Germany',
        'French': 'France', 'France': 'France',
        'British': 'Britain', 'Britain': 'Britain', 'UK': 'UK', 
        'United Kingdom': 'United Kingdom', 'England': 'England',
        'American': 'America', 'America': 'America', 'USA': 'USA', 
        'United States': 'United States',
        'Italian': 'Italy', 'Italy': 'Italy',
        'Spanish': 'Spain', 'Spain': 'Spain',
        'Russian': 'Russia', 'Russia': 'Russia',
        'Chinese': 'China', 'China': 'China',
        'Japanese': 'Japan', 'Japan': 'Japan',
    }
    
    for pattern in country_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            found = match.group(1)
            # Normalize to country name
            params["country"] = country_map.get(found, found)
            break
    
    # Extract years - look for 4-digit numbers (years)
    years = re.findall(r'\b(1\d{3}|2\d{3})\b', query)
    if len(years) >= 2:
        # Sort to get start and end
        year_ints = sorted([int(y) for y in years])
        params["start_year"] = year_ints[0]
        params["end_year"] = year_ints[-1]
    elif len(years) == 1:
        params["start_year"] = int(years[0])
        params["end_year"] = int(years[0])
    
    # Extract event_type - look for keywords
    event_types = []
    query_lower = query.lower()
    
    if 'war' in query_lower:
        event_types.append("War")
    if 'revolution' in query_lower:
        event_types.append("Revolutions")
    if 'diplomacy' in query_lower or 'diplomatic' in query_lower:
        event_types.append("Diplomacy")
    if 'economy' in query_lower or 'economic' in query_lower:
        event_types.append("Economy")
    
    # Only include event_type if we found specific types
    if event_types:
        params["event_type"] = event_types
    
    return {func_name: params}
