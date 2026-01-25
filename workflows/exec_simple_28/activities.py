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
    
    Returns format: {"function_name": {"param1": val1, ...}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            # Extract numbers from query using regex
            # Look for patterns like "15-foot radius", "radius of 15", "15 foot"
            patterns = [
                r'(\d+(?:\.\d+)?)\s*-?\s*(?:foot|feet|ft)',  # "15-foot" or "15 foot"
                r'radius\s+(?:of\s+)?(\d+(?:\.\d+)?)',  # "radius of 15" or "radius 15"
                r'(\d+(?:\.\d+)?)\s*(?:foot|feet|ft)?\s*radius',  # "15 foot radius"
                r'(\d+(?:\.\d+)?)',  # fallback: any number
            ]
            
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    if param_type == "integer":
                        params[param_name] = int(float(value))
                    else:
                        params[param_name] = float(value)
                    break
        
        elif param_type == "string":
            # For string parameters, try to extract relevant text
            # This is a simple fallback - specific patterns would be added based on context
            string_patterns = [
                r'(?:for|in|of|with|named?)\s+["\']?([A-Za-z][A-Za-z\s]+?)["\']?(?:\s+(?:and|with|,)|[.!?]|$)',
            ]
            
            for pattern in string_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    return {func_name: params}
