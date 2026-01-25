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
    
    # Parse prompt - may be JSON string with nested structure
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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    # Extract vehicle_type - look for gas, diesel, EV keywords
    vehicle_type_patterns = [
        (r'\bgas[-\s]?powered\b', 'gas'),
        (r'\bgasoline\b', 'gas'),
        (r'\bgas\b', 'gas'),
        (r'\bdiesel\b', 'diesel'),
        (r'\belectric\s*vehicle\b', 'EV'),
        (r'\bev\b', 'EV'),
        (r'\belectric\b', 'EV'),
    ]
    
    for pattern, vtype in vehicle_type_patterns:
        if re.search(pattern, query_lower):
            params["vehicle_type"] = vtype
            break
    
    # Extract miles_driven - look for number followed by "miles"
    miles_patterns = [
        r'(\d+(?:,\d{3})*)\s*miles',  # "1500 miles" or "1,500 miles"
        r'driving\s+(\d+(?:,\d{3})*)',  # "driving 1500"
        r'(\d+(?:,\d{3})*)\s*mi\b',  # "1500 mi"
    ]
    
    for pattern in miles_patterns:
        match = re.search(pattern, query_lower)
        if match:
            miles_str = match.group(1).replace(',', '')
            params["miles_driven"] = int(miles_str)
            break
    
    # Extract emission_factor if specified (optional parameter)
    emission_patterns = [
        r'emission\s*factor\s*(?:of|is|=|:)?\s*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*g/mile',
        r'factor\s*(?:of|is|=|:)?\s*(\d+(?:\.\d+)?)',
    ]
    
    for pattern in emission_patterns:
        match = re.search(pattern, query_lower)
        if match:
            params["emission_factor"] = float(match.group(1))
            break
    
    return {func_name: params}
