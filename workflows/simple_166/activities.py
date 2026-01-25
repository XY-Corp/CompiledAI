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
            # Extract user query from BFCL format
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    # Extract city - look for "in [City]" pattern
    city_match = re.search(r'\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)', query)
    if city_match:
        city = city_match.group(1).strip()
        # Add state abbreviation if it's a known city
        city_state_map = {
            "Chicago": "Chicago, IL",
            "New York": "New York, NY",
            "Los Angeles": "Los Angeles, CA",
            "Houston": "Houston, TX",
        }
        params["city"] = city_state_map.get(city, city)
    
    # Extract specialty - look for specialty keywords
    specialty_keywords = {
        "civil": "Civil",
        "divorce": "Divorce",
        "immigration": "Immigration",
        "business": "Business",
        "criminal": "Criminal"
    }
    specialties = []
    for keyword, value in specialty_keywords.items():
        if keyword in query_lower:
            specialties.append(value)
    if specialties:
        params["specialty"] = specialties
    
    # Extract fee - look for dollar amounts with "less than" or "under" patterns
    fee_match = re.search(r'(?:less\s+than|under|below|max(?:imum)?)\s*\$?\s*(\d+)', query_lower)
    if fee_match:
        params["fee"] = int(fee_match.group(1))
    else:
        # Try to find any dollar amount
        dollar_match = re.search(r'\$\s*(\d+)', query)
        if dollar_match:
            params["fee"] = int(dollar_match.group(1))
        else:
            # Try to find number followed by "dollars"
            dollars_match = re.search(r'(\d+)\s*dollars?', query_lower)
            if dollars_match:
                params["fee"] = int(dollars_match.group(1))
    
    return {func_name: params}
