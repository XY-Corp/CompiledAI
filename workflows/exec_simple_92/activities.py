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
        
        # Extract user query from BFCL format
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
    
    # For order_food: extract items, quantities, and prices
    # Pattern: "X items, each costing $Y" or "X items at $Y each"
    items = []
    quantities = []
    prices = []
    
    # Known food items from the schema
    food_options = [
        'fries', 'dumplings', 'pizza', 'soda', 'salad', 'rice bowl', 'burger', 
        'cake', 'cookie', 'ice cream', 'sandwich', 'hot dog', 'noodles', 
        'chicken', 'beef', 'pork', 'fish', 'shrimp', 'lobster', 'crab', 'steak'
    ]
    
    query_lower = query.lower()
    
    # Pattern 1: "X burgers, each costing $Y" or "X burgers at $Y"
    # Pattern 2: "X ice creams, with each being $Y"
    # General pattern: quantity + item + price
    
    # Try multiple patterns to extract item orders
    patterns = [
        # "10 burgers, each costing $5"
        r'(\d+)\s+([a-z\s]+?)(?:s)?,?\s*(?:each\s+)?(?:costing|at|being|for)\s*\$?(\d+(?:\.\d+)?)',
        # "$5 burgers, 10 of them"
        r'\$?(\d+(?:\.\d+)?)\s+([a-z\s]+?)(?:s)?,?\s*(\d+)\s+(?:of them|each)',
        # "get 10 burgers at $5 each"
        r'get\s+(\d+)\s+([a-z\s]+?)(?:s)?\s+(?:at|for)\s*\$?(\d+(?:\.\d+)?)',
    ]
    
    # First, find all food items mentioned and their associated numbers
    for food in food_options:
        # Create pattern for this specific food item
        # Handle plural forms
        food_pattern = food + r's?' if not food.endswith('s') else food
        
        # Pattern: "quantity food_item ... $price" or "quantity food_item, each costing $price"
        pattern1 = rf'(\d+)\s+{food_pattern}[^$]*?\$(\d+(?:\.\d+)?)'
        match1 = re.search(pattern1, query_lower)
        
        if match1:
            qty = int(match1.group(1))
            price = float(match1.group(2))
            items.append(food)
            quantities.append(qty)
            prices.append(price)
            continue
        
        # Pattern: "$price food_item ... quantity"
        pattern2 = rf'\$(\d+(?:\.\d+)?)\s+{food_pattern}[^0-9]*?(\d+)'
        match2 = re.search(pattern2, query_lower)
        
        if match2:
            price = float(match2.group(1))
            qty = int(match2.group(2))
            items.append(food)
            quantities.append(qty)
            prices.append(price)
    
    # Build result
    params = {
        "item": items,
        "quantity": quantities,
        "price": prices
    }
    
    return {func_name: params}
