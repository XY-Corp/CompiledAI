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
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract location - look for patterns like "my location, X" or "nearby X" or "in X"
    # Pattern: "my location, Manhattan" or "location, Manhattan" or "nearby Manhattan"
    location_patterns = [
        r'my location,?\s*([A-Za-z\s]+?)(?:,|\.|offering|with|$)',
        r'nearby\s+(?:my\s+)?(?:location,?\s*)?([A-Za-z\s]+?)(?:,|\.|offering|with|$)',
        r'in\s+([A-Za-z\s]+?)(?:,|\.|offering|with|$)',
        r'at\s+([A-Za-z\s]+?)(?:,|\.|offering|with|$)',
    ]
    
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up trailing words that aren't part of location
            location = re.sub(r'\s+(offering|with|and|for).*$', '', location, flags=re.IGNORECASE).strip()
            break
    
    if location and "location" in props:
        params["location"] = location
    
    # Extract food_type - look for cuisine types
    food_patterns = [
        r'offering\s+([A-Za-z]+)\s+food',
        r'([A-Za-z]+)\s+food',
        r'([A-Za-z]+)\s+cuisine',
        r'([A-Za-z]+)\s+restaurant',
    ]
    
    food_type = None
    for pattern in food_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            food_type = match.group(1).strip()
            # Skip generic words
            if food_type.lower() not in ['the', 'a', 'an', 'some', 'any', 'good', 'best', 'nearby']:
                break
            food_type = None
    
    if food_type and "food_type" in props:
        params["food_type"] = food_type
    
    # Extract number - find integers in the query
    numbers = re.findall(r'\b(\d+)\b', query)
    if numbers and "number" in props:
        params["number"] = int(numbers[0])
    
    # Extract dietary_requirements - look for dietary keywords
    dietary_keywords = ['vegan', 'vegetarian', 'gluten-free', 'gluten free', 'halal', 'kosher', 
                        'dairy-free', 'dairy free', 'nut-free', 'nut free', 'organic', 'keto',
                        'low-carb', 'low carb', 'paleo']
    
    dietary_requirements = []
    for keyword in dietary_keywords:
        if keyword.lower() in query_lower:
            # Normalize to hyphenated form
            normalized = keyword.replace(' ', '-')
            dietary_requirements.append(normalized)
    
    if dietary_requirements and "dietary_requirements" in props:
        params["dietary_requirements"] = dietary_requirements
    
    return {func_name: params}
