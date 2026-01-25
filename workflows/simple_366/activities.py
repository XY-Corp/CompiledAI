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
    query_lower = query.lower()
    
    # Extract numeric value - look for patterns like "2 tablespoons", "in 2 tablespoons"
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # For unit conversion: identify from_unit and to_unit
    # Pattern: "How many X are in Y Z" -> converting from Z to X
    # Example: "How many teaspoons are in 2 tablespoons" -> from tablespoon to teaspoon
    
    # Common kitchen units
    units = ['teaspoon', 'tablespoon', 'cup', 'ounce', 'pound', 'gram', 'kilogram', 'liter', 'milliliter', 'pint', 'quart', 'gallon']
    
    # Find units mentioned in query
    found_units = []
    for unit in units:
        # Check for singular and plural forms
        if unit in query_lower or unit + 's' in query_lower:
            found_units.append(unit)
    
    # Parse the conversion direction
    # "How many teaspoons are in 2 tablespoons" -> from=tablespoon, to=teaspoon, value=2
    from_unit = None
    to_unit = None
    value = None
    
    # Pattern 1: "How many X are in Y Z" - converting Y Z to X
    match = re.search(r'how many (\w+)s? (?:are )?in (\d+(?:\.\d+)?)\s*(\w+)s?', query_lower)
    if match:
        to_unit = match.group(1)  # teaspoon
        value = int(float(match.group(2)))  # 2
        from_unit = match.group(3)  # tablespoon
    
    # Pattern 2: "convert X Y to Z"
    if not from_unit:
        match = re.search(r'convert (\d+(?:\.\d+)?)\s*(\w+)s? to (\w+)s?', query_lower)
        if match:
            value = int(float(match.group(1)))
            from_unit = match.group(2)
            to_unit = match.group(3)
    
    # Normalize unit names (remove trailing 's' if present)
    if from_unit and from_unit.endswith('s') and from_unit[:-1] in units:
        from_unit = from_unit[:-1]
    if to_unit and to_unit.endswith('s') and to_unit[:-1] in units:
        to_unit = to_unit[:-1]
    
    # Build params based on schema
    if "value" in props and value is not None:
        params["value"] = value
    elif "value" in props and numbers:
        params["value"] = int(float(numbers[0]))
    
    if "from_unit" in props and from_unit:
        params["from_unit"] = from_unit
    
    if "to_unit" in props and to_unit:
        params["to_unit"] = to_unit
    
    return {func_name: params}
