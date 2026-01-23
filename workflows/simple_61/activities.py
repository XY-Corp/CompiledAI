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
    
    Parses the prompt to extract parameter values and returns them in the format
    {"function_name": {"param1": val1, "param2": val2}}.
    """
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    
    # Extract weight (look for number followed by "lbs" or "pounds")
    weight_match = re.search(r'(\d+)\s*(?:lbs?|pounds?)', query, re.IGNORECASE)
    if weight_match and "weight" in params_schema:
        params["weight"] = int(weight_match.group(1))
    
    # Extract height - handle feet and inches format
    # Pattern: "5ft 10in" or "5 feet 10 inches" or "5'10"" etc.
    height_match = re.search(r'(\d+)\s*(?:ft|feet|\')\s*(\d+)\s*(?:in|inches|")?', query, re.IGNORECASE)
    if height_match and "height" in params_schema:
        feet = int(height_match.group(1))
        inches = int(height_match.group(2))
        total_inches = feet * 12 + inches
        params["height"] = total_inches
    else:
        # Try just inches
        inches_match = re.search(r'(\d+)\s*(?:in|inches)', query, re.IGNORECASE)
        if inches_match and "height" in params_schema:
            params["height"] = int(inches_match.group(1))
    
    # Extract activity level - match against enum values
    if "activity_level" in params_schema:
        activity_enum = params_schema["activity_level"].get("enum", [])
        query_lower = query.lower()
        
        # Check for each enum value in the query
        for level in activity_enum:
            if level.lower() in query_lower:
                params["activity_level"] = level
                break
    
    return {func_name: params}
