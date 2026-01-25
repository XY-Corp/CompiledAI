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
        
        if param_type == "integer":
            # Extract integers from query
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                # Use the first number found for integer params
                params[param_name] = int(numbers[0])
        
        elif param_type == "boolean":
            # Check for explicit boolean indicators in query
            query_lower = query.lower()
            
            # Look for explicit formatting preferences
            if "formatted" in param_name.lower():
                # Default to true unless explicitly asking for array/list/raw
                if any(word in query_lower for word in ["array", "list", "raw", "unformatted"]):
                    params[param_name] = False
                else:
                    # Default to true as per description
                    params[param_name] = True
            else:
                # Generic boolean - check for true/false keywords
                if any(word in query_lower for word in ["true", "yes", "enable"]):
                    params[param_name] = True
                elif any(word in query_lower for word in ["false", "no", "disable"]):
                    params[param_name] = False
                else:
                    # Default based on description if available
                    desc = param_info.get("description", "").lower()
                    if "default is true" in desc:
                        params[param_name] = True
                    elif "default is false" in desc:
                        params[param_name] = False
                    else:
                        params[param_name] = True  # Safe default
        
        elif param_type == "string":
            # Extract string values - look for quoted strings or named entities
            quoted = re.findall(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted[0]
            else:
                # Try to extract based on common patterns
                match = re.search(r'(?:for|of|with|named?)\s+([A-Za-z\s]+?)(?:\s*$|[,.])', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
    
    return {func_name: params}
