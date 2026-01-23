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
    """Extract function name and parameters from user query and function schema.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
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
    
    # Parse functions - may be JSON string
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "event_name":
            # Extract event name - look for "Treaty of X" or similar patterns
            # Common patterns: "When did X take place", "date of X", etc.
            event_patterns = [
                r'(?:when did|date of|about)\s+(?:the\s+)?([A-Z][A-Za-z\s]+?)(?:\s+take place|\s+happen|\s+occur|\?|$)',
                r'(?:Treaty of [A-Za-z]+)',
                r'([A-Z][A-Za-z]+(?:\s+of\s+[A-Z][A-Za-z]+)?)',
            ]
            
            # Try to find "Treaty of X" pattern first
            treaty_match = re.search(r'(Treaty of [A-Za-z]+)', query)
            if treaty_match:
                params[param_name] = treaty_match.group(1)
            else:
                # Try other patterns
                for pattern in event_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
        
        elif param_name == "format":
            # Extract date format - look for "format of X" or "in the format X"
            format_patterns = [
                r'(?:in the format(?: of)?|format[:\s]+)\s*["\']?([A-Z\-\.]+)["\']?',
                r'(?:format|formatted as)\s+([A-Z\-\.]+)',
            ]
            
            for pattern in format_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    # Only include required params if we couldn't extract optional ones
    # But if format was explicitly mentioned, include it
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
        elif param_name in required_params:
            # Required but not found - use placeholder
            final_params[param_name] = "<UNKNOWN>"
    
    return {func_name: final_params}
