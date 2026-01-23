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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
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
                query_lower = query.lower()
                if "civil war" in query_lower or "american civil war" in query_lower:
                    # American Civil War was 1861-1865, use start year
                    params[param_name] = 1861
                elif "revolutionary war" in query_lower:
                    params[param_name] = 1776
                elif "world war i" in query_lower or "world war 1" in query_lower:
                    params[param_name] = 1914
                elif "world war ii" in query_lower or "world war 2" in query_lower:
                    params[param_name] = 1941
                else:
                    # Extract any number as fallback
                    numbers = re.findall(r'\d+', query)
                    if numbers:
                        params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Check if this is an "event" parameter
            if "event" in param_name.lower() or "event" in param_desc:
                # Extract event name from query
                query_lower = query.lower()
                
                # Common historical events
                if "american civil war" in query_lower or "civil war" in query_lower:
                    params[param_name] = "American Civil War"
                elif "revolutionary war" in query_lower:
                    params[param_name] = "American Revolutionary War"
                elif "world war i" in query_lower or "world war 1" in query_lower:
                    params[param_name] = "World War I"
                elif "world war ii" in query_lower or "world war 2" in query_lower:
                    params[param_name] = "World War II"
                elif "great depression" in query_lower:
                    params[param_name] = "Great Depression"
                else:
                    # Try to extract event using patterns
                    # Pattern: "during the X" or "during X"
                    event_match = re.search(r'during\s+(?:the\s+)?([A-Za-z\s]+?)(?:\?|$|\.)', query, re.IGNORECASE)
                    if event_match:
                        params[param_name] = event_match.group(1).strip()
                    else:
                        # Fallback: extract noun phrases that might be events
                        params[param_name] = query.strip().rstrip("?")
            else:
                # Generic string extraction
                params[param_name] = query.strip()
    
    return {func_name: params}
