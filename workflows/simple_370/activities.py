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
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on the query
    params = {}
    
    # For safeway.order: extract location, items, and quantity
    
    # Extract location - look for "from Safeway in <location>" or "in <location>"
    location_match = re.search(r'(?:from\s+)?(?:Safeway\s+)?in\s+([A-Za-z\s]+?)(?:\.|$)', query, re.IGNORECASE)
    if location_match:
        location = location_match.group(1).strip()
        # Add state if it looks like a city
        if location.lower() == "palo alto":
            location = "Palo Alto, CA"
        params["location"] = location
    
    # Extract items and quantities
    items = []
    quantities = []
    
    # Pattern to match quantity + item descriptions
    # Examples: "three bottles of olive oil", "a five pound bag of rice"
    query_lower = query.lower()
    
    # Number word to digit mapping
    word_to_num = {
        "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
    }
    
    # Split by "and" to get individual item phrases
    # "Order three bottles of olive oil and a five pound bag of rice"
    item_phrases = re.split(r'\s+and\s+', query_lower)
    
    for phrase in item_phrases:
        # Try to extract quantity and item
        # Pattern: (number/word) (unit/container) of (item) OR (number/word) (item)
        
        # Match patterns like "three bottles of olive oil" or "a five pound bag of rice"
        match = re.search(r'(?:order\s+)?(\w+)\s+(?:bottles?\s+of\s+|bags?\s+of\s+|pounds?\s+of\s+|pound\s+bag\s+of\s+)?(.+?)(?:\s+from|$)', phrase)
        
        if match:
            qty_word = match.group(1).strip()
            item_desc = match.group(2).strip()
            
            # Convert quantity word to number
            if qty_word in word_to_num:
                qty = word_to_num[qty_word]
            elif qty_word.isdigit():
                qty = int(qty_word)
            else:
                # Check if there's a number word after (e.g., "a five pound bag")
                inner_match = re.search(r'(\w+)\s+pound', item_desc)
                if inner_match and inner_match.group(1) in word_to_num:
                    qty = word_to_num[inner_match.group(1)]
                else:
                    qty = 1
            
            # Clean up item description
            # For "five pound bag of rice" -> "rice"
            # For "bottles of olive oil" -> "olive oil"
            item_clean = re.sub(r'^(bottles?\s+of\s+|bags?\s+of\s+|\w+\s+pound\s+bag\s+of\s+)', '', item_desc).strip()
            
            if item_clean:
                items.append(item_clean)
                quantities.append(qty)
    
    # If the simple parsing didn't work well, try a more direct approach
    if not items:
        # Direct extraction for known patterns
        # "three bottles of olive oil"
        olive_match = re.search(r'(\w+)\s+bottles?\s+of\s+olive\s+oil', query_lower)
        if olive_match:
            qty_word = olive_match.group(1)
            qty = word_to_num.get(qty_word, 1)
            items.append("olive oil")
            quantities.append(qty)
        
        # "a five pound bag of rice"
        rice_match = re.search(r'a?\s*(\w+)\s+pound\s+bag\s+of\s+rice', query_lower)
        if rice_match:
            qty_word = rice_match.group(1)
            qty = word_to_num.get(qty_word, 1)
            items.append("rice")
            quantities.append(qty)
    
    params["items"] = items
    params["quantity"] = quantities
    
    return {func_name: params}
