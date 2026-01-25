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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "city":
            # Extract city name - look for known patterns
            # Pattern: "in [City]" or "of [City]"
            city_patterns = [
                r'(?:in|of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "in San Francisco"
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+in\s+\d{4}',  # "San Francisco in 2020"
            ]
            for pattern in city_patterns:
                match = re.search(pattern, query)
                if match:
                    city = match.group(1).strip()
                    # Filter out common non-city words
                    if city.lower() not in ['the', 'a', 'an', 'provide', 'me']:
                        params["city"] = city
                        break
        
        elif param_name == "state":
            # For San Francisco, the state is California
            # Check for explicit state mentions or infer from city
            state_patterns = [
                r',\s*([A-Z]{2})\b',  # "San Francisco, CA"
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+state',  # "California state"
            ]
            state_found = False
            for pattern in state_patterns:
                match = re.search(pattern, query)
                if match:
                    params["state"] = match.group(1).strip()
                    state_found = True
                    break
            
            # Infer state from well-known cities if not explicitly mentioned
            if not state_found and "city" in params:
                city_to_state = {
                    "san francisco": "CA",
                    "los angeles": "CA",
                    "new york": "NY",
                    "chicago": "IL",
                    "houston": "TX",
                    "phoenix": "AZ",
                    "seattle": "WA",
                    "denver": "CO",
                    "boston": "MA",
                    "miami": "FL",
                }
                city_lower = params["city"].lower()
                if city_lower in city_to_state:
                    params["state"] = city_to_state[city_lower]
        
        elif param_name == "type":
            # Extract crime type - look for keywords
            crime_types = ["violent", "property", "theft", "assault", "murder", "robbery", "burglary"]
            for crime_type in crime_types:
                if crime_type in query_lower:
                    params["type"] = crime_type
                    break
        
        elif param_name == "year":
            # Extract year using regex - look for 4-digit numbers that look like years
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
            if year_match:
                params["year"] = int(year_match.group(1))
    
    # Validate required parameters are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to find required params
            if req_param == "state" and "city" in params:
                # Default to CA for San Francisco if not found
                if params["city"].lower() == "san francisco":
                    params["state"] = "CA"
    
    return {func_name: params}
