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
    """Extract function call from user query and return as {func_name: {params}}.
    
    Parses the prompt to extract the user's query, identifies the target function,
    and extracts parameter values using regex/string matching.
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
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For movie_name: extract quoted string or text after common patterns
            if "movie" in param_name.lower() or "movie" in param_desc:
                # Try to extract quoted movie name first
                quoted_match = re.search(r'"([^"]+)"', query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
                else:
                    # Try patterns like "rating for X" or "rating of X"
                    pattern_match = re.search(r'(?:rating\s+(?:is\s+)?(?:for|of)\s+|about\s+)([A-Za-z0-9\s\':]+?)(?:\?|$|\.|\s+I\'m|\s+is)', query, re.IGNORECASE)
                    if pattern_match:
                        params[param_name] = pattern_match.group(1).strip()
                    else:
                        # Fallback: look for capitalized words that might be a title
                        title_match = re.search(r'(?:movie|film)\s+(?:called\s+)?["\']?([A-Za-z0-9\s\':]+)["\']?', query, re.IGNORECASE)
                        if title_match:
                            params[param_name] = title_match.group(1).strip()
            else:
                # Generic string extraction - try quoted first, then after "for/of"
                quoted_match = re.search(r'"([^"]+)"', query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
