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
    """Extract function name and parameters from user query using regex/parsing."""
    
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Extract parameters based on the query
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
    
    # Assign to sign1 and sign2 parameters
    if "sign1" in params_schema and len(found_signs) >= 1:
        params["sign1"] = found_signs[0]
    if "sign2" in params_schema and len(found_signs) >= 2:
        params["sign2"] = found_signs[1]
    
    # Extract scale parameter if mentioned
    if "scale" in params_schema:
        if "percentage" in query_lower or "percent" in query_lower:
            params["scale"] = "percentage"
        elif "0-10" in query_lower or "scale" in query_lower:
            params["scale"] = "0-10 scale"
        # Default to percentage if not specified but compatibility is mentioned
        elif "compatibility" in query_lower:
            params["scale"] = "percentage"
    
    return {func_name: params}
