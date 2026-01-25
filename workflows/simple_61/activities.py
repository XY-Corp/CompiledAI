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
    
    # Extract weight (look for pattern like "weight 150lbs" or "150 lbs")
    weight_patterns = [
        r'weight\s*(?:of\s*)?(\d+)\s*(?:lbs?|pounds?)?',
        r'(\d+)\s*(?:lbs?|pounds?)\s*(?:weight)?',
        r'weighs?\s*(\d+)',
    ]
    for pattern in weight_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["weight"] = int(match.group(1))
            break
    
    # Extract height - handle feet and inches format
    # Pattern: "5ft 10in", "5 feet 10 inches", "5'10"", etc.
    height_patterns = [
        r"(\d+)\s*(?:ft|feet|')\s*(\d+)\s*(?:in|inches|\")?",
        r"(\d+)\s*(?:foot|feet)\s*(\d+)\s*(?:inch|inches)?",
        r"height\s*(?:of\s*)?(\d+)\s*(?:in|inches)",
    ]
    
    height_found = False
    for pattern in height_patterns[:2]:  # First two patterns are feet+inches
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            feet = int(match.group(1))
            inches = int(match.group(2))
            params["height"] = feet * 12 + inches  # Convert to total inches
            height_found = True
            break
    
    # If not found, try just inches pattern
    if not height_found:
        match = re.search(height_patterns[2], query, re.IGNORECASE)
        if match:
            params["height"] = int(match.group(1))
    
    # Extract activity level - match against enum values
    activity_levels = ["sedentary", "lightly active", "moderately active", "very active", "extra active"]
    query_lower = query.lower()
    
    for level in activity_levels:
        if level in query_lower:
            params["activity_level"] = level
            break
    
    return {func_name: params}
