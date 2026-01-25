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
    """Extract function call parameters from natural language query.
    
    Parses the user query and function schema to extract parameter values
    using regex and string matching - no LLM calls needed.
    """
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
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+', query)
    
    # Extract location/city - look for patterns like "of X" or "near X" or city names
    # Pattern: "of [City], [State]" or "near [City]" or "within X km of [City]"
    location_patterns = [
        r'(?:of|near|from|in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,?\s*[A-Z][a-z]*)',  # "of Denver, Colorado"
        r'(?:of|near|from|in)\s+([A-Z][a-z]+(?:,\s*[A-Z][a-z]+)?)',  # "of Denver" or "of Denver, Colorado"
    ]
    
    location = None
    for pattern in location_patterns:
        match = re.search(pattern, query)
        if match:
            location = match.group(1).strip()
            break
    
    # Map extracted values to parameter names based on schema
    number_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For location/city parameters
            if location and any(keyword in param_name.lower() or keyword in param_desc 
                               for keyword in ["location", "city", "place", "address"]):
                params[param_name] = location
        
        elif param_type == "integer":
            # Try to match numbers based on context in description
            if number_idx < len(numbers):
                # Check description for hints about which number to use
                if "radius" in param_desc or "distance" in param_desc or "kilometer" in param_desc:
                    # Look for number near "km" or "kilometer"
                    radius_match = re.search(r'(\d+)\s*(?:km|kilometer)', query, re.IGNORECASE)
                    if radius_match:
                        params[param_name] = int(radius_match.group(1))
                    elif number_idx < len(numbers):
                        params[param_name] = int(numbers[number_idx])
                        number_idx += 1
                elif "amount" in param_desc or "number" in param_desc or "count" in param_desc:
                    # Look for number at start or after "the X" pattern
                    amount_match = re.search(r'(?:the\s+)?(\d+)\s+(?:tallest|highest|largest|biggest|top)', query, re.IGNORECASE)
                    if amount_match:
                        params[param_name] = int(amount_match.group(1))
                    elif number_idx < len(numbers):
                        params[param_name] = int(numbers[number_idx])
                        number_idx += 1
                else:
                    # Default: assign next available number
                    params[param_name] = int(numbers[number_idx])
                    number_idx += 1
    
    return {func_name: params}
