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
    """Extract function name and parameters from user query using regex.
    
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
    
    # Extract parameters using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers from query
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                # Use the first number found for numeric parameters
                params[param_name] = int(numbers[0]) if param_type == "integer" else float(numbers[0])
        
        elif param_type == "boolean":
            # Check for explicit boolean mentions in query
            query_lower = query.lower()
            
            # Check for explicit true/false mentions
            if "formatted" in param_name.lower() or "format" in param_desc:
                # Default to true for formatted parameter unless explicitly false
                if "not formatted" in query_lower or "unformatted" in query_lower or "array" in query_lower:
                    params[param_name] = False
                else:
                    params[param_name] = True
            elif "true" in query_lower:
                params[param_name] = True
            elif "false" in query_lower:
                params[param_name] = False
            else:
                # Use default from description if available
                if "default is true" in param_desc or "default true" in param_desc:
                    params[param_name] = True
                elif "default is false" in param_desc or "default false" in param_desc:
                    params[param_name] = False
                else:
                    params[param_name] = True  # Default to true
        
        elif param_type == "string":
            # Extract string values based on context
            # Try common patterns like "for X" or "of X"
            string_match = re.search(r'(?:for|of|in|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,)|$)', query, re.IGNORECASE)
            if string_match:
                params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
