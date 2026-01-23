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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract years - look for 4-digit numbers
            years = re.findall(r'\b(1\d{3}|2\d{3})\b', query)
            
            if param_name == "start_year" and len(years) >= 1:
                # First year is typically start year
                params[param_name] = int(years[0])
            elif param_name == "end_year" and len(years) >= 2:
                # Second year is typically end year
                params[param_name] = int(years[1])
            elif param_name == "year" and len(years) >= 1:
                params[param_name] = int(years[0])
        
        elif param_type == "string":
            if param_name == "country":
                # Extract country name - look for patterns like "for <country>" or "of <country>"
                country_patterns = [
                    r'(?:for|of|in)\s+([A-Z][a-zA-Z\s]+?)(?:\s+from|\s+between|\s+during|\s*$)',
                    r'data\s+(?:for|of)\s+([A-Z][a-zA-Z\s]+)',
                    r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:from|between|during)',
                ]
                
                for pattern in country_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
            else:
                # Generic string extraction - look for quoted strings or after "for/of/in"
                match = re.search(r'(?:for|of|in)\s+([A-Za-z\s]+?)(?:\s+from|\s+to|\s*$)', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
    
    return {func_name: params}
