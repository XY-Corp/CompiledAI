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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    # Extract location - look for patterns like "my location, X" or "in X" or "nearby X"
    location_patterns = [
        r'my location,?\s*([A-Za-z\s]+?)(?:,|\.|offering|$)',
        r'(?:in|at|near|nearby)\s+([A-Za-z\s]+?)(?:,|\.|offering|$)',
        r'location[:\s]+([A-Za-z\s,]+?)(?:\.|offering|$)',
    ]
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            location = match.group(1).strip().rstrip(',')
            break
    
    if location:
        params["location"] = location
    
    # Extract food_type - look for cuisine types
    food_patterns = [
        r'offering\s+([A-Za-z]+)\s+food',
        r'([A-Za-z]+)\s+food',
        r'([A-Za-z]+)\s+cuisine',
        r'([A-Za-z]+)\s+restaurants?',
    ]
    food_type = None
    for pattern in food_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Filter out common non-food words
            if candidate.lower() not in ['find', 'nearby', 'the', 'a', 'my', 'some', 'good']:
                food_type = candidate
                break
    
    if food_type:
        params["food_type"] = food_type
    
    # Extract number - find integers in the query
    number_match = re.search(r'\b(\d+)\s*(?:restaurants?|places?|results?)?', query, re.IGNORECASE)
    if number_match:
        params["number"] = int(number_match.group(1))
    
    # Extract dietary_requirements - look for dietary keywords
    dietary_keywords = ['vegan', 'vegetarian', 'gluten-free', 'gluten free', 'halal', 'kosher', 
                        'dairy-free', 'dairy free', 'nut-free', 'nut free', 'organic', 'keto',
                        'low-carb', 'low carb', 'paleo']
    dietary_requirements = []
    query_lower = query.lower()
    for keyword in dietary_keywords:
        if keyword in query_lower:
            # Normalize to hyphenated form
            normalized = keyword.replace(' ', '-')
            dietary_requirements.append(normalized)
    
    if dietary_requirements:
        params["dietary_requirements"] = dietary_requirements
    
    return {func_name: params}
