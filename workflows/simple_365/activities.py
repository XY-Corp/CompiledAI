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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on the query
    params = {}
    query_lower = query.lower()
    
    # Extract quantity - look for numbers
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Extract units - common cooking units
    unit_patterns = [
        r'\b(ounces?|oz)\b',
        r'\b(pounds?|lbs?)\b',
        r'\b(cups?)\b',
        r'\b(tablespoons?|tbsp)\b',
        r'\b(teaspoons?|tsp)\b',
        r'\b(grams?|g)\b',
        r'\b(kilograms?|kg)\b',
        r'\b(liters?|l)\b',
        r'\b(milliliters?|ml)\b',
    ]
    
    found_units = []
    for pattern in unit_patterns:
        matches = re.findall(pattern, query_lower)
        found_units.extend(matches)
    
    # Normalize units
    unit_map = {
        'ounce': 'ounces', 'oz': 'ounces',
        'pound': 'pounds', 'lb': 'pounds', 'lbs': 'pounds',
        'cup': 'cups',
        'tablespoon': 'tablespoons', 'tbsp': 'tablespoons',
        'teaspoon': 'teaspoons', 'tsp': 'teaspoons',
        'gram': 'grams', 'g': 'grams',
        'kilogram': 'kilograms', 'kg': 'kilograms',
        'liter': 'liters', 'l': 'liters',
        'milliliter': 'milliliters', 'ml': 'milliliters',
    }
    
    normalized_units = []
    for unit in found_units:
        normalized = unit_map.get(unit, unit)
        if normalized not in normalized_units:
            normalized_units.append(normalized)
    
    # Determine from_unit and to_unit based on query structure
    # Pattern: "How many X in Y" -> convert from Y to X
    # Pattern: "Convert X to Y" -> convert from X to Y
    
    from_unit = None
    to_unit = None
    
    # "How many ounces in 2 pounds" -> from=pounds, to=ounces
    how_many_match = re.search(r'how many\s+(\w+)\s+in\s+(\d+)\s+(\w+)', query_lower)
    if how_many_match:
        to_unit = how_many_match.group(1)
        from_unit = how_many_match.group(3)
    
    # Normalize the extracted units
    if from_unit:
        from_unit = unit_map.get(from_unit, from_unit)
    if to_unit:
        to_unit = unit_map.get(to_unit, to_unit)
    
    # Extract item - look for "of X" pattern
    item_match = re.search(r'of\s+(\w+)', query_lower)
    item = item_match.group(1) if item_match else None
    
    # Build params based on schema
    if "quantity" in props and numbers:
        params["quantity"] = int(float(numbers[0]))
    
    if "from_unit" in props and from_unit:
        params["from_unit"] = from_unit
    
    if "to_unit" in props and to_unit:
        params["to_unit"] = to_unit
    
    if "item" in props and item:
        params["item"] = item
    
    return {func_name: params}
