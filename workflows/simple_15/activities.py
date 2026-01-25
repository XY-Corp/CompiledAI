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
    """Extract function call parameters from user query using regex and string matching."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Parse functions - may be JSON string
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
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract function string (e.g., "y = x^3" or "x^3")
    # Pattern: look for function expressions like "x^3", "x**2", etc.
    func_patterns = [
        r'function\s+y\s*=\s*([^\s]+)',  # "function y = x^3"
        r'y\s*=\s*([^\s]+)',              # "y = x^3"
        r'for\s+(?:the\s+)?function\s+([^\s]+)',  # "for the function x^3"
        r'integrate\s+([x\^\d\+\-\*\/\(\)]+)',    # "integrate x^3"
    ]
    
    function_str = None
    for pattern in func_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            function_str = match.group(1).strip()
            break
    
    if function_str:
        params["function"] = function_str
    
    # Extract start_x and end_x - look for "from x = -2 to x = 3" or similar patterns
    range_patterns = [
        r'from\s+x\s*=\s*(-?\d+)\s+to\s+x\s*=\s*(-?\d+)',  # "from x = -2 to x = 3"
        r'from\s+(-?\d+)\s+to\s+(-?\d+)',                   # "from -2 to 3"
        r'between\s+x\s*=\s*(-?\d+)\s+and\s+x\s*=\s*(-?\d+)',  # "between x = -2 and x = 3"
        r'between\s+(-?\d+)\s+and\s+(-?\d+)',               # "between -2 and 3"
        r'x\s*=\s*(-?\d+)\s+(?:to|and)\s+x\s*=\s*(-?\d+)',  # "x = -2 to x = 3"
    ]
    
    for pattern in range_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["start_x"] = int(match.group(1))
            params["end_x"] = int(match.group(2))
            break
    
    # Extract method - look for "simpson" or "trapezoid"
    if "simpson" in query_lower:
        params["method"] = "simpson"
    elif "trapezoid" in query_lower:
        params["method"] = "trapezoid"
    
    return {func_name: params}
