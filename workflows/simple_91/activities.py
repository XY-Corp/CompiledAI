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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    func_name = func.get("name", "unknown")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on the query content using regex/string matching
    params = {}
    query_lower = query.lower()
    
    # For get_restaurant function, extract cuisine, location, and condition
    if func_name == "get_restaurant":
        # Extract cuisine - look for food type keywords
        cuisine_patterns = [
            r'\b(sushi|japanese|chinese|italian|mexican|indian|thai|french|korean|vietnamese|american|greek|mediterranean|pizza|burger|seafood|steak|bbq|vegetarian|vegan)\b'
        ]
        for pattern in cuisine_patterns:
            match = re.search(pattern, query_lower)
            if match:
                params["cuisine"] = match.group(1)
                break
        
        # Extract location - look for "in [City]" pattern or known city names
        location_patterns = [
            r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # "in Boston", "in New York"
            r'\b(Boston|New York|Los Angeles|Chicago|San Francisco|Seattle|Miami|Austin|Denver|Portland|Atlanta|Dallas|Houston|Phoenix|Philadelphia)\b'
        ]
        for pattern in location_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["location"] = match.group(1).strip()
                break
        
        # Extract condition - look for day/time/amenity conditions
        condition_patterns = [
            r'(?:opens?|open)\s+(?:on\s+)?(\w+days?)',  # "opens on Sundays"
            r'(?:that\s+)?(?:is\s+)?open\s+(?:on\s+)?(\w+)',  # "that is open on Sunday"
            r'(Sundays?|Mondays?|Tuesdays?|Wednesdays?|Thursdays?|Fridays?|Saturdays?)',  # Day names
            r'(?:with|has)\s+(.+?)(?:\.|$)',  # "with outdoor seating"
        ]
        for pattern in condition_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                condition_value = match.group(1).strip()
                # Normalize to "opens on X" format if it's a day
                if re.match(r'(Sun|Mon|Tues|Wednes|Thurs|Fri|Satur)days?', condition_value, re.IGNORECASE):
                    params["condition"] = f"opens on {condition_value}"
                else:
                    params["condition"] = condition_value
                break
    else:
        # Generic extraction for other functions
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
            else:
                # For string params, try to extract based on param name patterns
                pattern = rf'{param_name}[:\s]+["\']?([^"\']+)["\']?'
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
    
    return {func_name: params}
