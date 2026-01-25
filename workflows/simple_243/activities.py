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
    
    Parses the user's natural language query to extract relevant parameters
    for the specified function schema.
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # For "discovery" parameter - extract what the user is asking about
            if "discovery" in param_name.lower() or "discovery" in param_desc:
                # Pattern: "Who discovered X?" or "discovered the X"
                patterns = [
                    r'who\s+discovered\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\?|\.|\s+give|\s+tell|$)',
                    r'discovered\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\?|\.|\s+give|\s+tell|$)',
                    r'discovery\s+of\s+(?:the\s+)?([a-zA-Z\s]+?)(?:\?|\.|\s+give|\s+tell|$)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                else:
                    # Fallback: extract key noun after "discovered"
                    match = re.search(r'discovered\s+(?:the\s+)?(\w+)', query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
        
        elif param_type == "boolean":
            # For "detail" parameter - check if user wants detailed info
            detail_keywords = ['detail', 'detailed', 'more info', 'additional', 'full', 'complete', 'in depth']
            query_lower = query.lower()
            
            # Check for detail-related keywords
            has_detail = any(kw in query_lower for kw in detail_keywords)
            params[param_name] = has_detail
        
        elif param_type == "integer" or param_type == "number":
            # Extract numbers from query
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
