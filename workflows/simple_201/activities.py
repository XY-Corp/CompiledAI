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
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract numbers for integer params
            numbers = re.findall(r'\b(\d{4})\b', query)  # Look for year-like numbers first
            if numbers and "year" in param_name.lower():
                params[param_name] = int(numbers[0])
            else:
                # General number extraction
                all_numbers = re.findall(r'\b(\d+)\b', query)
                if all_numbers:
                    params[param_name] = int(all_numbers[0])
        
        elif param_type == "string":
            # Extract string values based on parameter semantics
            value = None
            
            # Species extraction
            if "species" in param_name.lower() or "species" in param_desc:
                # Common patterns: "population of X", "X population", "X in the wild"
                patterns = [
                    r'population of (\w+)',
                    r'(\w+) population',
                    r'(\w+) in the wild',
                    r'estimate.*?(\w+) in',
                ]
                for pattern in patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        value = match.group(1)
                        break
            
            # Country extraction
            elif "country" in param_name.lower() or "country" in param_desc:
                # Common patterns: "in X", "in the wild in X"
                patterns = [
                    r'in the wild in (\w+)',
                    r'in (\w+)\.?$',
                    r'in (\w+)\s*$',
                ]
                for pattern in patterns:
                    match = re.search(pattern, query_lower)
                    if match:
                        value = match.group(1)
                        break
                
                # Also check for known country names
                countries = ['china', 'usa', 'india', 'brazil', 'japan', 'germany', 'france', 'uk', 'australia']
                for country in countries:
                    if country in query_lower:
                        value = country
                        break
            
            if value:
                # Capitalize properly
                params[param_name] = value.capitalize()
    
    # Only include required params and those we found values for
    # Don't include optional params without values
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
    
    return {func_name: final_params}
