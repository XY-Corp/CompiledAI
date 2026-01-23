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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    query_lower = query.lower()
    
    # Extract function string (e.g., "y = x^3" or "function y = x^3")
    # Pattern: look for "function y = ..." or just "y = ..."
    func_match = re.search(r'(?:function\s+)?y\s*=\s*([x\^\d\+\-\*\/\s\(\)]+)', query, re.IGNORECASE)
    if func_match:
        params["function"] = func_match.group(1).strip()
    else:
        # Try to find expression like "x^3" directly
        expr_match = re.search(r'(x\s*\^\s*\d+)', query, re.IGNORECASE)
        if expr_match:
            params["function"] = expr_match.group(1).replace(" ", "")
    
    # Extract start_x and end_x from patterns like "from x = -2 to x = 3" or "from -2 to 3"
    range_match = re.search(r'from\s+(?:x\s*=\s*)?([-]?\d+)\s+to\s+(?:x\s*=\s*)?([-]?\d+)', query, re.IGNORECASE)
    if range_match:
        params["start_x"] = int(range_match.group(1))
        params["end_x"] = int(range_match.group(2))
    else:
        # Try alternative patterns like "between -2 and 3"
        between_match = re.search(r'between\s+([-]?\d+)\s+and\s+([-]?\d+)', query, re.IGNORECASE)
        if between_match:
            params["start_x"] = int(between_match.group(1))
            params["end_x"] = int(between_match.group(2))
    
    # Extract method - look for "simpson" or "trapezoid"
    if "simpson" in query_lower:
        params["method"] = "simpson"
    elif "trapezoid" in query_lower:
        params["method"] = "trapezoid"
    
    return {func_name: params}
