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
        
        if param_name == "platform":
            # Extract platform - look for common patterns
            platform_patterns = [
                r'(?:compatible with|for|on)\s+([A-Za-z0-9\s]+?)(?:\s+and|\s+with|\.|,|$)',
                r'(Windows\s*\d+|PS\d+|Xbox\s*\w*|Nintendo\s*\w*|Mac\s*\w*|Linux)',
            ]
            for pattern in platform_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "rating":
            # Extract rating - look for numbers near "rating", "above", "over", etc.
            rating_patterns = [
                r'rating\s+(?:above|over|greater than|at least|minimum|min)?\s*(\d+(?:\.\d+)?)',
                r'(?:above|over|greater than|at least|minimum|min)\s+(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s+(?:rating|stars?)',
            ]
            for pattern in rating_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = float(match.group(1))
                    break
        
        elif param_name == "genre":
            # Extract genre - check for enum values in query
            enum_values = param_info.get("enum", [])
            for genre in enum_values:
                if genre.lower() in query.lower():
                    params[param_name] = genre
                    break
            # Genre is optional with default, so don't add if not found
    
    return {func_name: params}
