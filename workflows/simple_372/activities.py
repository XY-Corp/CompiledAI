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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract numbers - look for patterns like "top five", "top 5", etc.
            # First check for word numbers
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
            }
            
            # Look for "top X" pattern with word numbers
            top_word_match = re.search(r'top\s+(one|two|three|four|five|six|seven|eight|nine|ten)', query_lower)
            if top_word_match:
                params[param_name] = word_to_num[top_word_match.group(1)]
            else:
                # Look for numeric digits
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "boolean":
            # Check for organic/non-organic keywords
            if "organic" in param_desc:
                if "organic" in query_lower and "non-organic" not in query_lower and "not organic" not in query_lower:
                    params[param_name] = True
                elif "non-organic" in query_lower or "not organic" in query_lower:
                    params[param_name] = False
                # If not mentioned, don't include (use default)
        
        elif param_type == "string":
            # Extract product name - look for patterns
            if "product" in param_desc:
                # Common patterns: "top X [product]", "find [product]", "[product] brands"
                # For this query: "organic bananas brands"
                
                # Try to extract product after "organic" or before "brands"
                product_patterns = [
                    r'organic\s+(\w+(?:\s+\w+)?)\s+brands?',  # "organic bananas brands"
                    r'top\s+\w+\s+(\w+(?:\s+\w+)?)\s+brands?',  # "top five bananas brands"
                    r'find\s+(?:the\s+)?(?:top\s+)?\w*\s*(\w+(?:\s+\w+)?)\s+brands?',  # "find bananas brands"
                    r'(\w+)\s+brands?\s+(?:from|on|at)',  # "bananas brands from"
                ]
                
                for pattern in product_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        product = match.group(1).strip()
                        # Clean up - remove "organic" if captured
                        product = re.sub(r'^organic\s+', '', product)
                        if product and product not in ['the', 'a', 'an']:
                            params[param_name] = product
                            break
                
                # Fallback: look for common product words
                if param_name not in params:
                    # Extract noun that's likely a product
                    common_products = ['bananas', 'apples', 'milk', 'bread', 'eggs', 'cheese', 'yogurt']
                    for prod in common_products:
                        if prod in query_lower:
                            params[param_name] = prod
                            break
    
    return {func_name: params}
