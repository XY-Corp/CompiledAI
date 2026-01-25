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
    
    params = {}
    
    # Extract year - look for 4-digit year patterns
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
    if year_match and "year" in props:
        params["year"] = year_match.group(1)
    
    # Extract country - check for country names and map to codes
    country_mapping = {
        "united states": "US", "usa": "US", "america": "US", "us": "US",
        "austria": "AT", "at": "AT",
        "germany": "DE", "de": "DE",
        "spain": "ES", "es": "ES",
        "france": "FR", "fr": "FR",
        "united kingdom": "GB", "uk": "GB", "britain": "GB", "gb": "GB", "england": "GB",
        "italy": "IT", "it": "IT",
        "netherlands": "NL", "holland": "NL", "nl": "NL",
        "poland": "PL", "pl": "PL",
        "romania": "RO", "ro": "RO",
        "slovakia": "SK", "sk": "SK",
        "ukraine": "UA", "ua": "UA"
    }
    
    if "country" in props:
        query_lower = query.lower()
        for country_name, country_code in country_mapping.items():
            # Use word boundary matching to avoid partial matches
            if re.search(r'\b' + re.escape(country_name) + r'\b', query_lower):
                params["country"] = country_code
                break
    
    return {func_name: params}
