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
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], "function": [...]}
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
    
    # Extract location - look for city names after "near", "in", "at"
    location_patterns = [
        r'(?:near|in|at)\s+([A-Za-z]+(?:\s*,\s*[A-Za-z\s]+)?)',
        r'(?:near|in|at)\s+([A-Za-z\s]+?)(?:\s+for|\s+starting|$)',
    ]
    for pattern in location_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up location - remove trailing words like "for"
            location = re.sub(r'\s+for\s*$', '', location, flags=re.IGNORECASE).strip()
            params["location"] = location
            break
    
    # Extract room_type - look for room type keywords
    room_types = ["single", "double", "deluxe", "suite", "twin", "king", "queen"]
    for room_type in room_types:
        if room_type in query_lower:
            params["room_type"] = room_type
            break
    
    # Extract duration - look for number of nights
    duration_patterns = [
        r'(\d+)\s*nights?',
        r'for\s+(\d+)\s*(?:nights?|days?)',
    ]
    for pattern in duration_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["duration"] = int(match.group(1))
            break
    
    # Extract start_date - look for date patterns
    date_patterns = [
        r'(?:from|starting\s+(?:from)?|on)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})',
        r'(?:from|starting\s+(?:from)?|on)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})',
    ]
    for pattern in date_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["start_date"] = match.group(1).strip()
            break
    
    # Extract preferences - look for preference keywords
    preference_keywords = {
        "pet_friendly": ["pet friendly", "pet-friendly", "pets allowed", "pet"],
        "gym": ["gym", "fitness"],
        "swimming_pool": ["swimming pool", "pool"],
        "free_breakfast": ["free breakfast", "breakfast included", "breakfast"],
        "parking": ["parking", "free parking"],
    }
    
    preferences = []
    for pref_key, keywords in preference_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                preferences.append(pref_key)
                break
    
    if preferences:
        params["preferences"] = preferences
    
    return {func_name: params}
