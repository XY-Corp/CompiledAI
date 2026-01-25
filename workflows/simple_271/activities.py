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
    
    Parses the prompt to extract the function name and parameters based on
    the provided function schema. Returns format: {"function_name": {params}}.
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    
    # Extract building_id - look for patterns like "building Id B1004" or "building_id B1004"
    building_id_match = re.search(r'building\s*(?:Id|ID|id)?\s*([A-Z]?\d+[A-Z]?\d*)', query, re.IGNORECASE)
    if not building_id_match:
        # Try pattern like "B1004"
        building_id_match = re.search(r'\b([A-Z]\d{3,})\b', query)
    
    if building_id_match and "building_id" in params_schema:
        params["building_id"] = building_id_match.group(1)
    
    # Extract floors - look for ordinal numbers (2nd, 3rd, 4th) or cardinal numbers
    floors = []
    
    # Pattern for ordinal numbers: "2nd, 3rd and 4th floors"
    ordinal_pattern = r'(\d+)(?:st|nd|rd|th)'
    ordinal_matches = re.findall(ordinal_pattern, query, re.IGNORECASE)
    if ordinal_matches:
        floors = [int(f) for f in ordinal_matches]
    
    # If no ordinals found, try to find floor numbers in other patterns
    if not floors:
        # Pattern: "floors 2, 3, 4" or "floor 2 3 4"
        floor_section_match = re.search(r'floors?\s*([\d,\s]+)', query, re.IGNORECASE)
        if floor_section_match:
            floor_nums = re.findall(r'\d+', floor_section_match.group(1))
            floors = [int(f) for f in floor_nums]
    
    if floors and "floors" in params_schema:
        params["floors"] = floors
    
    # Extract mode - look for 'static' or 'dynamic'
    if "mode" in params_schema:
        if re.search(r'\bdynamic\b', query, re.IGNORECASE):
            params["mode"] = "dynamic"
        elif re.search(r'\bstatic\b', query, re.IGNORECASE):
            params["mode"] = "static"
        # If neither found explicitly, check for related keywords
        elif re.search(r'\bstructural\s+dynamic\b', query, re.IGNORECASE):
            params["mode"] = "dynamic"
    
    return {func_name: params}
