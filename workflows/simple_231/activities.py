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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
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
    query_lower = query.lower()
    
    # Extract country - look for country names
    # Pattern: "in X history" or "X history" or "for X"
    country_patterns = [
        r'\b(german|germany|french|france|british|britain|uk|american|america|usa|us|chinese|china|japanese|japan|russian|russia|italian|italy|spanish|spain|indian|india)\b',
    ]
    
    country_map = {
        'german': 'Germany', 'germany': 'Germany',
        'french': 'France', 'france': 'France',
        'british': 'Britain', 'britain': 'Britain', 'uk': 'UK',
        'american': 'America', 'america': 'America', 'usa': 'USA', 'us': 'US',
        'chinese': 'China', 'china': 'China',
        'japanese': 'Japan', 'japan': 'Japan',
        'russian': 'Russia', 'russia': 'Russia',
        'italian': 'Italy', 'italy': 'Italy',
        'spanish': 'Spain', 'spain': 'Spain',
        'indian': 'India', 'india': 'India',
    }
    
    for pattern in country_patterns:
        match = re.search(pattern, query_lower)
        if match:
            country_key = match.group(1).lower()
            params["country"] = country_map.get(country_key, country_key.capitalize())
            break
    
    # Extract years - look for 4-digit numbers (years)
    years = re.findall(r'\b(1\d{3}|2\d{3})\b', query)
    years = [int(y) for y in years]
    
    if len(years) >= 2:
        # Sort to get start and end
        years.sort()
        params["start_year"] = years[0]
        params["end_year"] = years[-1]
    elif len(years) == 1:
        # Single year - use as both start and end
        params["start_year"] = years[0]
        params["end_year"] = years[0]
    
    # Extract event_type - look for keywords
    event_types = []
    event_keywords = {
        'war': 'War',
        'wars': 'War',
        'military': 'War',
        'battle': 'War',
        'battles': 'War',
        'revolution': 'Revolutions',
        'revolutions': 'Revolutions',
        'revolt': 'Revolutions',
        'uprising': 'Revolutions',
        'diplomacy': 'Diplomacy',
        'diplomatic': 'Diplomacy',
        'treaty': 'Diplomacy',
        'treaties': 'Diplomacy',
        'economy': 'Economy',
        'economic': 'Economy',
        'trade': 'Economy',
        'financial': 'Economy',
    }
    
    for keyword, event_type in event_keywords.items():
        if keyword in query_lower and event_type not in event_types:
            event_types.append(event_type)
    
    # Only add event_type if found (it's optional with default 'all')
    if event_types:
        params["event_type"] = event_types
    
    return {func_name: params}
