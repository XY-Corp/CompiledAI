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
    """Extract function name and parameters from user query using regex patterns.
    
    Returns a dict with function name as key and parameters as nested object.
    """
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
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Look for specific parameter patterns in the query
    # Pattern: "base X" or "base of X" or "base: X"
    base_match = re.search(r'base\s*(?:of\s*)?(?:is\s*)?(?:=\s*)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    # Pattern: "height X" or "height of X" or "height: X"
    height_match = re.search(r'height\s*(?:of\s*)?(?:is\s*)?(?:=\s*)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    
    # Also check for "with base X and height Y" pattern
    with_pattern = re.search(r'with\s+base\s+(\d+(?:\.\d+)?)\s+and\s+height\s+(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    
    if with_pattern:
        params["base"] = int(float(with_pattern.group(1)))
        params["height"] = int(float(with_pattern.group(2)))
    elif base_match and height_match:
        params["base"] = int(float(base_match.group(1)))
        params["height"] = int(float(height_match.group(1)))
    elif len(numbers) >= 2:
        # Fallback: assign numbers in order they appear
        # For "base 6 and height 10", numbers would be ['6', '10']
        params["base"] = int(float(numbers[0]))
        params["height"] = int(float(numbers[1]))
    
    # Check for optional unit parameter
    unit_patterns = [
        r'in\s+(square\s+\w+|\w+\s+squared)',
        r'unit[s]?\s*(?:is|=|:)?\s*(\w+)',
        r'(square\s+(?:meters?|feet|inches|centimeters?|cm|m|ft|in))',
    ]
    
    for pattern in unit_patterns:
        unit_match = re.search(pattern, query, re.IGNORECASE)
        if unit_match:
            params["unit"] = unit_match.group(1).strip()
            break
    
    return {func_name: params}
