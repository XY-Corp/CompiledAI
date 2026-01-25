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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
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
    
    # Extract location (loc parameter)
    # Pattern: "near X", "in X", "at X", "from X"
    loc_patterns = [
        r'(?:near|in|at|from)\s+([A-Za-z\s]+?)(?:\.|,|$|\s+(?:show|get|find|buy|purchase))',
        r'(?:near|in|at|from)\s+([A-Za-z\s]+)',
    ]
    
    for pattern in loc_patterns:
        loc_match = re.search(pattern, query, re.IGNORECASE)
        if loc_match:
            loc = loc_match.group(1).strip()
            # Clean up trailing words that aren't part of location
            loc = re.sub(r'\s+(show|get|find|buy|purchase|I|want|to).*$', '', loc, flags=re.IGNORECASE).strip()
            if loc:
                params["loc"] = loc
                break
    
    # Extract product list
    # Look for patterns like "buy X, Y, and Z" or "X, Y, and Z from"
    products = []
    
    # Pattern: items listed with commas and "and"
    # "apples, rice, and 12 pack of bottled water"
    product_pattern = r'(?:buy|purchase|get|want)\s+(.+?)(?:\s+from|\s+at|\s+near|\.|\?|$)'
    product_match = re.search(product_pattern, query, re.IGNORECASE)
    
    if product_match:
        product_text = product_match.group(1).strip()
        
        # Split by comma and "and"
        # Handle "X, Y, and Z" pattern
        items = re.split(r',\s*(?:and\s+)?|\s+and\s+', product_text)
        
        for item in items:
            item = item.strip()
            if item:
                # Clean up the item name, but keep pack size info for later extraction
                products.append(item)
    
    # Extract pack sizes from product names and clean product names
    pack_sizes = []
    cleaned_products = []
    
    for product in products:
        # Look for pack size patterns: "12 pack of X", "X pack", "pack of 12"
        pack_match = re.search(r'(\d+)\s*pack(?:\s+of)?', product, re.IGNORECASE)
        
        if pack_match:
            pack_size = int(pack_match.group(1))
            pack_sizes.append(pack_size)
            # Clean the product name - extract what comes after "pack of"
            cleaned = re.sub(r'\d+\s*pack\s+of\s+', '', product, flags=re.IGNORECASE).strip()
            if not cleaned:
                # If nothing left, try to get what's before the pack number
                cleaned = re.sub(r'\d+\s*pack.*', '', product, flags=re.IGNORECASE).strip()
            if not cleaned:
                # Last resort - just use "bottled water" or similar
                cleaned = re.sub(r'^\d+\s*pack\s*(?:of\s*)?', '', product, flags=re.IGNORECASE).strip()
            cleaned_products.append(cleaned if cleaned else product)
        else:
            cleaned_products.append(product)
            # No pack size specified for this item
    
    if cleaned_products:
        params["product_list"] = cleaned_products
    
    # Only include pack_size if at least one was specified
    if pack_sizes:
        # Pad pack_sizes to match product_list length if needed
        while len(pack_sizes) < len(cleaned_products):
            pack_sizes.append(1)  # Default pack size
        params["pack_size"] = pack_sizes
    
    return {func_name: params}
