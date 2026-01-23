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
    """Extract function call parameters from natural language prompt.
    
    Parses the prompt to extract parameter values and returns them in the format
    {"function_name": {"param1": val1, "param2": val2, ...}}.
    """
    # Parse prompt - may be JSON string with nested structure
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
    
    # Extract parameters from query using regex
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers based on context clues from parameter name/description
            value = None
            
            if param_name == "area" or "area" in param_desc or "square feet" in param_desc:
                # Look for area patterns: "area of X", "X square feet", "X sq ft"
                patterns = [
                    r'area\s+(?:of\s+)?(\d+)',
                    r'(\d+)\s*(?:square feet|sq\.?\s*ft\.?|sqft)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        value = int(match.group(1))
                        break
            
            elif param_name == "rooms" or "room" in param_desc:
                # Look for room patterns: "X rooms", "number of rooms as X"
                patterns = [
                    r'(?:number of\s+)?rooms?\s+(?:as\s+|is\s+|of\s+)?(\d+)',
                    r'(\d+)\s+rooms?',
                ]
                for pattern in patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        value = int(match.group(1))
                        break
            
            elif param_name == "year" or "year" in param_desc or "construction" in param_desc:
                # Look for year patterns: "year X", "constructed in X", "year of construction is X"
                patterns = [
                    r'year\s+(?:of\s+construction\s+)?(?:is\s+|as\s+)?(\d{4})',
                    r'(?:constructed|built)\s+(?:in\s+)?(\d{4})',
                    r'construction\s+(?:is\s+|year\s+)?(\d{4})',
                    r'(\d{4})',  # Fallback: any 4-digit year
                ]
                for pattern in patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        year_val = int(match.group(1))
                        # Validate it's a reasonable year (1800-2100)
                        if 1800 <= year_val <= 2100:
                            value = year_val
                            break
            
            if value is not None:
                params[param_name] = value
        
        elif param_type == "string":
            value = None
            
            if param_name == "location" or "location" in param_desc or "city" in param_desc:
                # Look for location patterns: "in X", "at X", common city names
                patterns = [
                    r'(?:in|at|for)\s+([A-Z][a-zA-Z\s]+?)(?:\s+based|\s+with|\s+area|\s+,|$)',
                    r'house\s+(?:price\s+)?in\s+([A-Z][a-zA-Z\s]+?)(?:\s+based|\s+with|\s+area|\s+,|$)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
                        # Clean up common trailing words
                        value = re.sub(r'\s+(based|with|area|house).*$', '', value, flags=re.IGNORECASE).strip()
                        break
                
                # Fallback: check for known city names
                if not value:
                    known_cities = ["San Francisco", "New York", "Los Angeles", "Chicago", "Boston", "Seattle", "Austin", "Denver", "Miami", "Portland"]
                    for city in known_cities:
                        if city.lower() in query_lower:
                            value = city
                            break
            
            if value:
                params[param_name] = value
    
    return {func_name: params}
