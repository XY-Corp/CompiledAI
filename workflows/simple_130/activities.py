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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
                else:
                    query = str(prompt)
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
    
    # Extract cash_flows array - look for array pattern like [-50000, 10000, ...]
    if "cash_flows" in props:
        # Match array pattern with numbers (including negative)
        array_match = re.search(r'\[[\s\d,\-\.]+\]', query)
        if array_match:
            try:
                cash_flows = json.loads(array_match.group(0))
                params["cash_flows"] = cash_flows
            except json.JSONDecodeError:
                # Fallback: extract all numbers
                numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
                params["cash_flows"] = [int(n) if '.' not in n else float(n) for n in numbers]
    
    # Extract discount_rate - look for percentage pattern
    if "discount_rate" in props:
        # Match patterns like "8%", "8 percent", "at 8%", "discounted at 8%"
        rate_patterns = [
            r'(?:at|rate[:\s]+|discounted at)\s*(\d+(?:\.\d+)?)\s*%',
            r'(\d+(?:\.\d+)?)\s*%\s*(?:annually|annual|rate|interest)',
            r'(\d+(?:\.\d+)?)\s*%',
        ]
        
        for pattern in rate_patterns:
            rate_match = re.search(pattern, query, re.IGNORECASE)
            if rate_match:
                # Convert percentage to decimal (8% -> 0.08)
                rate_value = float(rate_match.group(1)) / 100
                params["discount_rate"] = rate_value
                break
    
    # Extract years if present (optional parameter)
    if "years" in props:
        # Look for explicit years array or year mentions
        years_match = re.search(r'years?\s*[:\s]*\[[\s\d,]+\]', query, re.IGNORECASE)
        if years_match:
            try:
                years_array_match = re.search(r'\[[\s\d,]+\]', years_match.group(0))
                if years_array_match:
                    params["years"] = json.loads(years_array_match.group(0))
            except json.JSONDecodeError:
                pass
        # If no explicit years array, don't include it (use default)
    
    return {func_name: params}
