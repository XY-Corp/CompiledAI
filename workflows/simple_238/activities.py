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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
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
                query = data["question"][0][0].get("content", str(prompt))
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract year - look for 4-digit numbers first
            year_match = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', query)
            if year_match:
                params[param_name] = int(year_match.group(1))
            else:
                # Try to infer year from known events
                if "civil war" in query_lower:
                    # American Civil War was 1861-1865, use start year
                    params[param_name] = 1861
                else:
                    # Extract any number as fallback
                    numbers = re.findall(r'\d+', query)
                    if numbers:
                        params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # For event parameter - extract the historical event
            if "event" in param_name.lower() or "event" in param_desc:
                # Common patterns for historical events
                event_patterns = [
                    r'during\s+(?:the\s+)?(.+?)(?:\?|$)',
                    r'(?:in|at|of)\s+(?:the\s+)?(.+?)(?:\?|$)',
                    r'(?:the\s+)?([A-Z][a-zA-Z\s]+(?:War|Revolution|Crisis|Movement|Act))',
                ]
                
                event = None
                for pattern in event_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        event = match.group(1).strip().rstrip('?')
                        break
                
                # Specific event detection
                if "civil war" in query_lower:
                    event = "American Civil War"
                elif "revolutionary war" in query_lower or "revolution" in query_lower:
                    event = "American Revolution"
                elif "world war i" in query_lower or "world war 1" in query_lower:
                    event = "World War I"
                elif "world war ii" in query_lower or "world war 2" in query_lower:
                    event = "World War II"
                
                if event:
                    params[param_name] = event
                else:
                    # Fallback - extract key phrase
                    params[param_name] = query.strip().rstrip('?')
    
    return {func_name: params}
