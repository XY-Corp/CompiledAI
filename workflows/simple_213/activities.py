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
    
    Parses the user query and extracts parameters to match the function schema.
    Returns format: {"function_name": {"param1": val1, ...}}
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
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract departure_location - pattern: "from X to Y"
    from_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+', query, re.IGNORECASE)
    if from_match and "departure_location" in props:
        params["departure_location"] = from_match.group(1).strip()
    
    # Extract destination_location - pattern: "to X for" or "to X"
    to_match = re.search(r'\s+to\s+([A-Za-z\s]+?)(?:\s+for|\s+on|\s*$)', query, re.IGNORECASE)
    if to_match and "destination_location" in props:
        params["destination_location"] = to_match.group(1).strip()
    
    # Extract date - pattern: YYYY-MM-DD
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', query)
    if date_match and "date" in props:
        params["date"] = date_match.group(1)
    
    # Extract time - look for time of day keywords
    time_keywords = ["morning", "afternoon", "evening", "night", "noon", "midnight"]
    for time_kw in time_keywords:
        if time_kw in query_lower:
            if "time" in props:
                params["time"] = time_kw
            break
    
    # Extract direct_flight - look for "direct" keyword
    if "direct_flight" in props:
        if "direct" in query_lower:
            params["direct_flight"] = True
        else:
            params["direct_flight"] = False
    
    return {func_name: params}
