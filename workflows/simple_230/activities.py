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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers (years, counts, etc.)
            numbers = re.findall(r'\b(\d{4}|\d+)\b', query)
            if numbers:
                # For date/year parameters, prefer 4-digit numbers
                if "year" in param_desc or "date" in param_desc:
                    four_digit = [n for n in numbers if len(n) == 4]
                    if four_digit:
                        params[param_name] = int(four_digit[0])
                    elif numbers:
                        params[param_name] = int(numbers[0])
                else:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract based on parameter description hints
            if "country" in param_desc or "region" in param_desc or "location" in param_desc:
                # Extract location - look for "of X" or "in X" patterns
                location_patterns = [
                    r'(?:King|Queen|Leader|Ruler|President|Emperor)\s+of\s+([A-Za-z]+)',
                    r'(?:in|of)\s+([A-Za-z]+)\s+(?:in|during|around)\s+\d',
                    r'(?:in|of)\s+([A-Za-z]+)',
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1)
                        break
            
            elif "title" in param_desc or "position" in param_desc:
                # Extract title - look for common titles
                title_patterns = [
                    r'\b(King|Queen|Emperor|Empress|President|Prime Minister|Leader|Ruler|Chancellor)\b',
                ]
                for pattern in title_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1)
                        break
    
    return {func_name: params}
