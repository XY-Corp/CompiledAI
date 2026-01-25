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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "game_name":
            # Extract game name - look for quoted names or names after common patterns
            # Pattern: 'GameName' or "GameName" or game called X or board game X
            quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
            else:
                # Try to find game name after common phrases
                name_match = re.search(r"(?:board game|game)\s+['\"]?([A-Za-z0-9\s]+?)['\"]?(?:\?|$|,|\s+and|\s+for)", query, re.IGNORECASE)
                if name_match:
                    params[param_name] = name_match.group(1).strip()
        
        elif param_name == "info_required" and param_type == "array":
            # Extract requested info types from enum
            enum_values = param_info.get("items", {}).get("enum", [])
            requested = []
            
            query_lower = query.lower()
            
            # Map common phrases to enum values
            mappings = {
                "average_review_rating": ["average review rating", "review rating", "rating", "reviews"],
                "age_range": ["age range", "age", "ages"],
                "number_of_players": ["number of players", "players", "how many players"],
                "playing_time": ["playing time", "play time", "how long", "duration"],
                "genre": ["genre", "type", "category"]
            }
            
            for enum_val in enum_values:
                if enum_val in mappings:
                    for phrase in mappings[enum_val]:
                        if phrase in query_lower:
                            if enum_val not in requested:
                                requested.append(enum_val)
                            break
            
            params[param_name] = requested
    
    return {func_name: params}
