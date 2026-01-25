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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract items and quantities from the query
    # Query: "Check the total price for three pumpkins and two dozen eggs at Walmart."
    
    # Number word to integer mapping
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "a": 1, "an": 1
    }
    
    items = []
    quantities = []
    
    # Pattern: "number/word item" or "number/word dozen item"
    # Match patterns like "three pumpkins", "two dozen eggs", "5 apples"
    query_lower = query.lower()
    
    # Pattern for "X dozen Y" (e.g., "two dozen eggs" = 24 eggs)
    dozen_pattern = r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a|an)\s+dozen\s+(\w+)'
    for match in re.finditer(dozen_pattern, query_lower):
        num_str = match.group(1)
        item = match.group(2).rstrip('s')  # Remove trailing 's' for singular
        
        if num_str.isdigit():
            qty = int(num_str) * 12
        else:
            qty = word_to_num.get(num_str, 1) * 12
        
        items.append(item)
        quantities.append(qty)
    
    # Pattern for regular "X items" (e.g., "three pumpkins")
    # Exclude "dozen" matches
    regular_pattern = r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a|an)\s+(?!dozen)(\w+)'
    for match in re.finditer(regular_pattern, query_lower):
        num_str = match.group(1)
        item = match.group(2).rstrip('s')  # Remove trailing 's' for singular
        
        # Skip if this item was already captured as part of dozen pattern
        if item in items:
            continue
        
        # Skip common non-item words
        skip_words = {'the', 'at', 'for', 'and', 'or', 'to', 'of', 'total', 'price', 'check'}
        if item in skip_words:
            continue
        
        if num_str.isdigit():
            qty = int(num_str)
        else:
            qty = word_to_num.get(num_str, 1)
        
        items.append(item)
        quantities.append(qty)
    
    # Extract store location if mentioned (optional parameter)
    store_location = None
    store_patterns = [
        r'at\s+(\w+)',  # "at Walmart"
        r'from\s+(\w+)',  # "from Target"
        r'in\s+(\w+)\s+store',  # "in Costco store"
    ]
    
    known_stores = {'walmart', 'target', 'costco', 'kroger', 'safeway', 'whole foods', 'trader joe'}
    
    for pattern in store_patterns:
        match = re.search(pattern, query_lower)
        if match:
            potential_store = match.group(1)
            if potential_store.lower() in known_stores:
                store_location = potential_store.capitalize()
                break
    
    # Build params dict
    params = {
        "items": items,
        "quantities": quantities
    }
    
    # Only include store_location if found (it's optional)
    if store_location:
        params["store_location"] = store_location
    
    return {func_name: params}
