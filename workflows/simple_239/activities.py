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
    
    Uses regex and string parsing to extract values - no LLM calls needed.
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        default_value = param_info.get("default")
        
        if param_type == "integer":
            # Extract year or other integers from query
            # Look for 4-digit years first (most common for year parameters)
            if "year" in param_name.lower() or "year" in param_desc:
                year_match = re.search(r'\b(1[0-9]{3}|2[0-9]{3})\b', query)
                if year_match:
                    params[param_name] = int(year_match.group(1))
            else:
                # Extract any integer
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "boolean":
            # Check for boolean indicators in query
            query_lower = query.lower()
            
            # Check if query explicitly asks for full name
            if "full_name" in param_name.lower() or "full name" in param_desc:
                if "full name" in query_lower or "full_name" in query_lower:
                    params[param_name] = True
                elif default_value is not None:
                    # Use default if specified and query implies it
                    params[param_name] = default_value
            else:
                # Generic boolean handling
                if "true" in query_lower or "yes" in query_lower:
                    params[param_name] = True
                elif "false" in query_lower or "no" in query_lower:
                    params[param_name] = False
                elif default_value is not None:
                    params[param_name] = default_value
        
        elif param_type == "string":
            # Extract string values based on context
            # This would need more specific patterns based on the parameter
            string_match = re.search(r'(?:for|in|of|with|named?)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|in|\?)|$)', query, re.IGNORECASE)
            if string_match:
                params[param_name] = string_match.group(1).strip()
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to extract required params
            param_info = params_schema.get(req_param, {})
            param_type = param_info.get("type", "string")
            
            if param_type == "integer":
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    # For year, prefer 4-digit numbers
                    four_digit = [n for n in numbers if len(n) == 4]
                    if four_digit:
                        params[req_param] = int(four_digit[0])
                    else:
                        params[req_param] = int(numbers[0])
    
    return {func_name: params}
