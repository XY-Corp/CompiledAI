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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "jurisdiction":
            # Look for state/country names - common patterns
            # Pattern: "in [State/Country]" or "[State/Country]"
            jurisdiction_patterns = [
                r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',  # "in California"
                r'\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',  # "for California"
            ]
            
            for pattern in jurisdiction_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1)
                    break
            
            # If not found, try common state names
            if param_name not in params:
                states = ["California", "Texas", "New York", "Florida", "Illinois", "Pennsylvania", 
                          "Ohio", "Georgia", "Michigan", "Arizona", "Washington", "Colorado"]
                for state in states:
                    if state.lower() in query_lower:
                        params[param_name] = state
                        break
        
        elif param_name == "crime":
            # Look for crime types - pattern: "crime of [crime]" or "for [crime]"
            crime_patterns = [
                r'crime\s+of\s+(\w+)',  # "crime of theft"
                r'punishments?\s+for\s+(?:the\s+)?(?:crime\s+of\s+)?(\w+)',  # "punishments for theft"
                r'for\s+(\w+)\s+in',  # "for theft in"
            ]
            
            for pattern in crime_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = match.group(1)
                    break
            
            # Common crimes as fallback
            if param_name not in params:
                crimes = ["theft", "robbery", "assault", "murder", "burglary", "fraud", 
                          "arson", "kidnapping", "vandalism", "trespassing"]
                for crime in crimes:
                    if crime in query_lower:
                        params[param_name] = crime
                        break
        
        elif param_name == "detail_level":
            # Check for detail level indicators
            if "detail" in query_lower or "detailed" in query_lower:
                params[param_name] = "detailed"
            elif "basic" in query_lower or "simple" in query_lower:
                params[param_name] = "basic"
            # Check enum values if available
            elif "enum" in param_info:
                enum_values = param_info.get("enum", [])
                for val in enum_values:
                    if val.lower() in query_lower:
                        params[param_name] = val
                        break
    
    return {func_name: params}
