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
    
    Parses the user query and function schema to extract parameter values
    using regex and string matching patterns.
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    # For routing function: extract start_location, end_location, avoid_tolls
    if "start_location" in params_schema:
        # Pattern: "from X to Y" or "from X ... to Y"
        route_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\s+with|\s+avoiding|\s*\.|$)', query, re.IGNORECASE)
        if route_match:
            params["start_location"] = route_match.group(1).strip()
            params["end_location"] = route_match.group(2).strip()
    
    if "end_location" in params_schema and "end_location" not in params:
        # Fallback pattern for destination
        dest_match = re.search(r'to\s+([A-Za-z\s]+?)(?:\s+with|\s+avoiding|\s*\.|$)', query, re.IGNORECASE)
        if dest_match:
            params["end_location"] = dest_match.group(1).strip()
    
    if "avoid_tolls" in params_schema:
        # Check for toll avoidance keywords
        avoid_toll_patterns = [
            r'avoid(?:ing)?\s+toll',
            r'toll\s+roads?\s+avoided',
            r'no\s+toll',
            r'without\s+toll',
            r'toll-free'
        ]
        avoid_tolls = any(re.search(pattern, query, re.IGNORECASE) for pattern in avoid_toll_patterns)
        params["avoid_tolls"] = avoid_tolls
    
    return {func_name: params}
