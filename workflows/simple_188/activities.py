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
    """Extract function name and parameters from user query using regex and string matching."""
    
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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # Extract location/city - look for patterns like "in [City], [State]" or "in [City]"
            if "location" in param_name or "city" in param_desc:
                # Pattern: "in City, State" or "in City State" or "for City"
                location_patterns = [
                    r'(?:in|for|at)\s+([A-Z][a-zA-Z]+(?:\s*,?\s*[A-Z][a-zA-Z]+)?)',  # "in Miami, Florida"
                    r'(?:in|for|at)\s+([A-Z][a-zA-Z\s,]+?)(?:\s+(?:in|for|over|during|the|upcoming|next|\d))',  # before time words
                ]
                
                for pattern in location_patterns:
                    match = re.search(pattern, query)
                    if match:
                        location = match.group(1).strip().rstrip(',')
                        params[param_name] = location
                        break
        
        elif param_type == "integer":
            # Extract days - look for number followed by "days" or "day"
            if "days" in param_name or "day" in param_desc:
                days_patterns = [
                    r'(?:upcoming|next|following|for)\s+(\d+)\s+days?',  # "upcoming 7 days"
                    r'(\d+)\s+days?\s+(?:forecast|ahead|from)',  # "7 days forecast"
                    r'(\d+)-day',  # "7-day"
                ]
                
                for pattern in days_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        params[param_name] = int(match.group(1))
                        break
            
            # Extract other integer params (like min_humidity) - only if explicitly mentioned
            elif "humidity" in param_name or "humidity" in param_desc:
                # Look for explicit minimum humidity mention
                humidity_patterns = [
                    r'(?:min(?:imum)?|at least)\s+(\d+)\s*%?\s*humidity',
                    r'humidity\s+(?:above|over|greater than|at least)\s+(\d+)',
                ]
                
                for pattern in humidity_patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        params[param_name] = int(match.group(1))
                        break
    
    return {func_name: params}
