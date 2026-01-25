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
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract numbers - look for patterns like "next 3 days", "for 5 days"
            number_patterns = [
                r'(?:next|for|past|last)\s+(\d+)\s+days?',
                r'(\d+)\s+days?',
                r'(\d+)',
            ]
            for pattern in number_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_type == "string":
            # Check if this is a location/city parameter
            if "city" in param_desc or "location" in param_desc:
                # Extract city name - look for patterns like "in Austin", "for Boston"
                city_patterns = [
                    r'(?:in|for|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s+for|\s+over|\s+in|\s*$)',
                    r'(?:in|for|at)\s+([A-Z][a-zA-Z]+)',
                ]
                for pattern in city_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
            
            # Check if this is a temperature unit parameter
            elif "unit" in param_desc or "celsius" in param_desc or "fahrenheit" in param_desc:
                if "celsius" in query_lower:
                    params[param_name] = "Celsius"
                elif "fahrenheit" in query_lower:
                    params[param_name] = "Fahrenheit"
                # If not specified and not required, skip (use default)
            
            else:
                # Generic string extraction - try to find quoted strings or key phrases
                quoted_match = re.search(r'"([^"]+)"', query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
    
    return {func_name: params}
