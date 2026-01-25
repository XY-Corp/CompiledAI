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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "name":
            # Extract board game name - look for quoted name or after "board game"
            # Pattern: 'Game Name' or "Game Name"
            quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
            if quoted_match:
                params["name"] = quoted_match.group(1)
            else:
                # Try to extract after "board game" or "game"
                game_match = re.search(r"(?:board\s+)?game\s+['\"]?([A-Za-z0-9\s]+)['\"]?", query, re.IGNORECASE)
                if game_match:
                    params["name"] = game_match.group(1).strip()
        
        elif param_name == "parameters" and param_type == "array":
            # Extract requested characteristics from enum options
            enum_options = param_info.get("items", {}).get("enum", [])
            found_params = []
            
            query_lower = query.lower()
            for option in enum_options:
                # Check if option or its variations appear in query
                option_lower = option.lower()
                # Handle variations: "player count" matches "player count", "players"
                if option_lower in query_lower:
                    found_params.append(option)
                elif option_lower == "player count" and ("player" in query_lower or "players" in query_lower):
                    found_params.append(option)
                elif option_lower == "rating" and "rating" in query_lower:
                    found_params.append(option)
                elif option_lower == "playing time" and ("time" in query_lower or "duration" in query_lower):
                    found_params.append(option)
                elif option_lower == "age" and "age" in query_lower:
                    found_params.append(option)
                elif option_lower == "mechanics" and "mechanic" in query_lower:
                    found_params.append(option)
            
            if found_params:
                params["parameters"] = found_params
        
        elif param_name == "language":
            # Only include if explicitly mentioned (it has a default)
            lang_match = re.search(r"(?:in|language[:\s]+)(\w+)", query, re.IGNORECASE)
            if lang_match:
                params["language"] = lang_match.group(1)
    
    return {func_name: params}
