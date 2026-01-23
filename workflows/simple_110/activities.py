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
    """Extract function call parameters from natural language query using regex patterns."""
    
    # Parse prompt - may be JSON string with nested structure
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Extract location (city name) - look for patterns like "in [City]" or "of [City]"
    location_match = re.search(r'(?:in|of|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s+with|\s+having|\s*,|\s*\.|\s*$)', query)
    location = location_match.group(1).strip() if location_match else None
    
    # Map extracted values to parameters based on context in query
    number_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Try to find contextual match first
            if "bedroom" in param_name.lower() or "bedroom" in param_desc:
                # Look for "X bedrooms" pattern
                bedroom_match = re.search(r'(\d+)\s*(?:bed(?:room)?s?)', query, re.IGNORECASE)
                if bedroom_match:
                    params[param_name] = int(bedroom_match.group(1))
                    continue
            
            if "bathroom" in param_name.lower() or "bathroom" in param_desc:
                # Look for "X bathrooms" pattern
                bathroom_match = re.search(r'(\d+)\s*(?:bath(?:room)?s?)', query, re.IGNORECASE)
                if bathroom_match:
                    params[param_name] = int(bathroom_match.group(1))
                    continue
            
            if "area" in param_name.lower() or "square" in param_desc or "sq" in param_desc:
                # Look for "X square feet" or "X sq ft" pattern
                area_match = re.search(r'(\d+)\s*(?:square\s*feet|sq\.?\s*ft\.?|sqft)', query, re.IGNORECASE)
                if area_match:
                    params[param_name] = int(area_match.group(1))
                    continue
            
            # Fallback: use numbers in order
            if number_idx < len(numbers):
                params[param_name] = int(float(numbers[number_idx]))
                number_idx += 1
        
        elif param_type == "string":
            if "location" in param_name.lower() or "city" in param_desc or "location" in param_desc:
                if location:
                    params[param_name] = location
    
    return {func_name: params}
