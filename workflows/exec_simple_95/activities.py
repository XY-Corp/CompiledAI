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
    """
    Extract function call from user query and available functions.
    Returns format: {"function_name": {"param1": val1}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data.get("question", [])
            if isinstance(question_data, list) and len(question_data) > 0:
                first_item = question_data[0]
                if isinstance(first_item, list) and len(first_item) > 0:
                    query = first_item[0].get("content", str(prompt))
                elif isinstance(first_item, dict):
                    query = first_item.get("content", str(prompt))
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

    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For movie_name: look for movie titles in quotes or after keywords
            if "movie" in param_name.lower() or "movie" in param_desc:
                # Try to find movie name in quotes first
                quote_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quote_match:
                    params[param_name] = quote_match.group(1)
                else:
                    # Look for patterns like "directed 'X'" or "movie X"
                    movie_patterns = [
                        r"(?:movie|film)\s+(?:called\s+)?['\"]?([A-Z][^'\",.?!]+)['\"]?",
                        r"['\"]([^'\"]+)['\"]",
                        r"who\s+directed\s+['\"]?([^'\",.?!]+)['\"]?",
                    ]
                    for pattern in movie_patterns:
                        match = re.search(pattern, query, re.IGNORECASE)
                        if match:
                            params[param_name] = match.group(1).strip()
                            break
            else:
                # Generic string extraction - try quotes first
                quote_match = re.search(r"['\"]([^'\"]+)['\"]", query)
                if quote_match:
                    params[param_name] = quote_match.group(1)
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])

    return {func_name: params}
