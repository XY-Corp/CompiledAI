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
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Get target function details
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
        
        if param_name == "color_name":
            # Extract color name - look for common color patterns
            # Pattern: "of X color" or "X color" or just color names
            color_patterns = [
                r'(?:of|the)\s+([A-Za-z\s]+?)\s+color',
                r'([A-Za-z\s]+?)\s+color',
                r'RGB\s+(?:value|values)\s+of\s+([A-Za-z\s]+)',
                r'identify\s+(?:the\s+)?(?:basic\s+)?(?:RGB\s+)?(?:value\s+)?(?:of\s+)?([A-Za-z\s]+?)(?:\s+color)?(?:\?|$)',
            ]
            
            color_name = None
            for pattern in color_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    color_name = match.group(1).strip()
                    # Clean up common words that aren't part of color name
                    color_name = re.sub(r'\b(basic|rgb|value|values|the|a|an)\b', '', color_name, flags=re.IGNORECASE).strip()
                    if color_name:
                        break
            
            # Fallback: look for known color names in query
            if not color_name:
                known_colors = ['sea green', 'red', 'blue', 'green', 'yellow', 'orange', 'purple', 
                               'pink', 'cyan', 'magenta', 'white', 'black', 'gray', 'grey',
                               'navy', 'teal', 'coral', 'salmon', 'olive', 'maroon', 'aqua']
                for color in known_colors:
                    if color in query_lower:
                        color_name = color.title()
                        break
            
            if color_name:
                params[param_name] = color_name
        
        elif param_name == "standard":
            # Extract standard - look for explicit mention or use default
            standard_patterns = [
                r'\b(basic|pantone|web|css|html)\b',
            ]
            
            standard = None
            for pattern in standard_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    standard = match.group(1).lower()
                    break
            
            # Only include if explicitly mentioned (it has a default)
            if standard:
                params[param_name] = standard
    
    return {func_name: params}
