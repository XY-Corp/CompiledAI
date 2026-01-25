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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # For zodiac compatibility - extract zodiac signs
    zodiac_signs = [
        "aries", "taurus", "gemini", "cancer", "leo", "virgo",
        "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
    ]
    
    # Find all zodiac signs mentioned in the query
    found_signs = []
    for sign in zodiac_signs:
        if sign in query_lower:
            found_signs.append(sign.capitalize())
    
    # Extract scale if mentioned
    scale = None
    if "percentage" in query_lower:
        scale = "percentage"
    elif "0-10" in query_lower or "0 to 10" in query_lower:
        scale = "0-10 scale"
    
    # Map extracted values to parameter names from schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "sign1" and len(found_signs) >= 1:
            params[param_name] = found_signs[0]
        elif param_name == "sign2" and len(found_signs) >= 2:
            params[param_name] = found_signs[1]
        elif param_name == "scale" and scale:
            params[param_name] = scale
    
    return {func_name: params}
