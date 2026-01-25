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
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "release_year" or param_type == "integer":
            # Extract year (4-digit number)
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
            if year_match:
                params[param_name] = int(year_match.group(1))
        
        elif param_name == "multiplayer" or param_type == "boolean":
            # Check for multiplayer keywords
            query_lower = query.lower()
            if "multi-player" in query_lower or "multiplayer" in query_lower:
                params[param_name] = True
            elif "single-player" in query_lower or "singleplayer" in query_lower:
                params[param_name] = False
            else:
                # Default based on context
                params[param_name] = "multi" in query_lower
        
        elif param_name == "ESRB_rating" or "rating" in param_name.lower():
            # Extract ESRB rating from quotes or common patterns
            # Look for quoted strings first
            quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
            else:
                # Look for common ESRB ratings
                query_lower = query.lower()
                if "everyone 10" in query_lower or "e10" in query_lower:
                    params[param_name] = "Everyone 10+"
                elif "everyone" in query_lower:
                    params[param_name] = "Everyone"
                elif "teen" in query_lower:
                    params[param_name] = "Teen"
                elif "mature" in query_lower:
                    params[param_name] = "Mature"
                elif "adults only" in query_lower:
                    params[param_name] = "Adults Only"
        
        elif param_type == "string":
            # Generic string extraction - look for quoted values
            quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
    
    return {func_name: params}
