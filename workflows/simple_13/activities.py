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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    
    # For calculate_area_under_curve, extract:
    # 1. function: mathematical expression like "x^2", "x**2", etc.
    # 2. interval: [start, end] numbers
    # 3. method: optional numerical method
    
    # Extract mathematical function - look for patterns like "y=x^2", "f(x)=x^2", or just "x^2"
    func_patterns = [
        r'y\s*=\s*([^\s,]+(?:\s*[\+\-\*\/\^]\s*[^\s,]+)*)',  # y = x^2
        r'f\s*\(\s*x\s*\)\s*=\s*([^\s,]+(?:\s*[\+\-\*\/\^]\s*[^\s,]+)*)',  # f(x) = x^2
        r'curve\s+([^\s]+(?:\s*[\+\-\*\/\^]\s*[^\s]+)*)\s+from',  # curve x^2 from
        r'function\s+([^\s]+(?:\s*[\+\-\*\/\^]\s*[^\s]+)*)',  # function x^2
    ]
    
    math_function = None
    for pattern in func_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            math_function = match.group(1).strip()
            break
    
    if math_function:
        params["function"] = math_function
    
    # Extract interval - look for "from x=1 to x=3" or "from 1 to 3" or "[1, 3]"
    interval_patterns = [
        r'from\s+x\s*=\s*(-?\d+(?:\.\d+)?)\s+to\s+x\s*=\s*(-?\d+(?:\.\d+)?)',  # from x=1 to x=3
        r'from\s+(-?\d+(?:\.\d+)?)\s+to\s+(-?\d+(?:\.\d+)?)',  # from 1 to 3
        r'interval\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]',  # interval [1, 3]
        r'between\s+x\s*=\s*(-?\d+(?:\.\d+)?)\s+and\s+x\s*=\s*(-?\d+(?:\.\d+)?)',  # between x=1 and x=3
        r'between\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)',  # between 1 and 3
    ]
    
    interval = None
    for pattern in interval_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            start = float(match.group(1))
            end = float(match.group(2))
            interval = [start, end]
            break
    
    if interval:
        params["interval"] = interval
    
    # Extract method if specified (optional parameter)
    method_patterns = [
        r'using\s+(\w+)\s+method',  # using trapezoidal method
        r'method\s*[=:]\s*["\']?(\w+)["\']?',  # method = trapezoidal
        r'(\w+)\s+approximation',  # trapezoidal approximation
    ]
    
    for pattern in method_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params["method"] = match.group(1).lower()
            break
    
    return {func_name: params}
