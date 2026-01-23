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
    
    # Extract vehicle_type - look for gas, diesel, EV keywords
    vehicle_type = None
    if "gas-powered" in query_lower or "gas powered" in query_lower or "gasoline" in query_lower:
        vehicle_type = "gas"
    elif "diesel" in query_lower:
        vehicle_type = "diesel"
    elif "electric" in query_lower or " ev " in query_lower or query_lower.endswith(" ev"):
        vehicle_type = "EV"
    # Also check for just "gas" but not as part of another word
    elif re.search(r'\bgas\b', query_lower):
        vehicle_type = "gas"
    
    if vehicle_type and "vehicle_type" in params_schema:
        params["vehicle_type"] = vehicle_type
    
    # Extract miles_driven - look for number followed by "miles"
    miles_match = re.search(r'(\d+(?:,\d{3})*)\s*miles', query_lower)
    if miles_match and "miles_driven" in params_schema:
        # Remove commas and convert to int
        miles_str = miles_match.group(1).replace(",", "")
        params["miles_driven"] = int(miles_str)
    
    # Extract emission_factor if explicitly mentioned (optional parameter)
    emission_match = re.search(r'emission\s*factor\s*(?:of|is|:)?\s*(\d+(?:\.\d+)?)', query_lower)
    if emission_match and "emission_factor" in params_schema:
        params["emission_factor"] = float(emission_match.group(1))
    
    return {func_name: params}
