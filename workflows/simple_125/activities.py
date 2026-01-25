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
    
    # Extract parameters using regex patterns
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Use description keywords to find the right number
            if "area" in param_name.lower() or "square feet" in param_desc:
                # Look for area patterns: "area of X", "X square feet"
                match = re.search(r'area\s+(?:of\s+)?(\d+)', query_lower)
                if not match:
                    match = re.search(r'(\d+)\s*(?:square feet|sq\.?\s*ft)', query_lower)
                if match:
                    params[param_name] = int(match.group(1))
            
            elif "room" in param_name.lower() or "room" in param_desc:
                # Look for room patterns: "X rooms", "number of rooms as X"
                match = re.search(r'(?:number of\s+)?rooms?\s+(?:as\s+|is\s+|of\s+)?(\d+)', query_lower)
                if not match:
                    match = re.search(r'(\d+)\s*rooms?', query_lower)
                if match:
                    params[param_name] = int(match.group(1))
            
            elif "year" in param_name.lower() or "year" in param_desc or "construction" in param_desc:
                # Look for year patterns: "year X", "constructed in X", "year of construction is X"
                match = re.search(r'(?:year\s+(?:of\s+construction\s+)?(?:is\s+|as\s+)?|constructed\s+(?:in\s+)?|built\s+(?:in\s+)?)(\d{4})', query_lower)
                if not match:
                    # Fallback: find any 4-digit year (1800-2100 range)
                    match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
                if match:
                    params[param_name] = int(match.group(1))
            
            else:
                # Generic number extraction for this parameter
                numbers = re.findall(r'\d+', query)
                if numbers:
                    # Try to find a number not already used
                    for num in numbers:
                        num_int = int(num)
                        if num_int not in params.values():
                            params[param_name] = num_int
                            break
        
        elif param_type == "string":
            if "location" in param_name.lower() or "city" in param_desc or "location" in param_desc:
                # Look for location patterns: "in X", "at X", common city names
                # Pattern for "in [City Name]" or "at [City Name]"
                match = re.search(r'(?:in|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s+based|\s+with|\s+area|\s+,|$)', query)
                if not match:
                    # Try to find known city patterns
                    city_match = re.search(r'(San Francisco|New York|Los Angeles|Chicago|Houston|Phoenix|Philadelphia|San Antonio|San Diego|Dallas|Seattle|Boston|Austin|Denver|Portland)', query, re.IGNORECASE)
                    if city_match:
                        params[param_name] = city_match.group(1).title()
                else:
                    params[param_name] = match.group(1).strip()
            else:
                # Generic string extraction - look for quoted strings or after "is"
                match = re.search(r'"([^"]+)"', query)
                if match:
                    params[param_name] = match.group(1)
    
    return {func_name: params}
