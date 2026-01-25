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
    """Extract function call from user query. Returns {"func_name": {params}}."""
    
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "string":
            # For movie_name: extract quoted string or text after key phrases
            # Pattern 1: Look for quoted strings (movie titles are often quoted)
            quoted_match = re.search(r'"([^"]+)"', query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
            else:
                # Pattern 2: Look for "movie X" or "the movie X" or "film X"
                movie_match = re.search(r'(?:the\s+)?(?:movie|film)\s+["\']?([A-Za-z0-9\s:]+?)["\']?(?:\s+(?:at|for|is|to|from|in|on|this|,|\.|$))', query, re.IGNORECASE)
                if movie_match:
                    params[param_name] = movie_match.group(1).strip()
                else:
                    # Pattern 3: Look for "rating for X" or "rating of X"
                    rating_match = re.search(r'rating\s+(?:for|of)\s+["\']?([A-Za-z0-9\s:]+?)["\']?(?:\s+(?:for|is|to|from|in|on|\?|,|\.|$))', query, re.IGNORECASE)
                    if rating_match:
                        params[param_name] = rating_match.group(1).strip()
                    else:
                        params[param_name] = ""
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
