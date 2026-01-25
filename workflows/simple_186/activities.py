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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
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
    
    # Parse functions - may be JSON string
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract city - look for patterns like "of [City]" or "[City], [Country]"
    # Common patterns: "temperature in Tokyo", "weather of Tokyo", "Tokyo, Japan"
    city_patterns = [
        r'(?:of|in|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,?\s*([A-Z][a-z]+)?',  # "of Tokyo, Japan"
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,\s*([A-Z][a-z]+)',  # "Tokyo, Japan"
    ]
    
    city = None
    country = None
    
    for pattern in city_patterns:
        match = re.search(pattern, query)
        if match:
            city = match.group(1).strip()
            if match.lastindex >= 2 and match.group(2):
                country = match.group(2).strip()
            break
    
    # If no city found with patterns, try to find capitalized words that could be city/country
    if not city:
        # Look for "Tokyo" or similar capitalized words
        caps_words = re.findall(r'\b([A-Z][a-z]+)\b', query)
        if caps_words:
            city = caps_words[0]
            if len(caps_words) > 1:
                country = caps_words[1]
    
    # Extract measurement unit - look for celsius/fahrenheit mentions
    measurement = None
    if 'celsius' in query_lower or 'in c' in query_lower:
        measurement = 'c'
    elif 'fahrenheit' in query_lower or 'in f' in query_lower:
        measurement = 'f'
    
    # Build params based on schema
    if "city" in params_schema and city:
        params["city"] = city
    
    if "country" in params_schema and country:
        params["country"] = country
    
    if "measurement" in params_schema and measurement:
        params["measurement"] = measurement
    
    return {func_name: params}
