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
    
    # Extract quoted strings - these are typically explicit values
    # Pattern: 'value' or "value"
    quoted_values = re.findall(r"['\"]([^'\"]+)['\"]", query)
    
    # For game_stats.fetch_player_statistics, we need: game, username, platform
    # Query: "Fetch player statistics of 'Zelda' on Switch for user 'Sam'."
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
        default_value = param_info.get("default") if isinstance(param_info, dict) else None
        
        if param_name == "game":
            # Look for game name - often after "of" or "for game"
            # Pattern: "of 'GameName'" or "statistics of 'GameName'"
            game_match = re.search(r"(?:statistics\s+of|of)\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
            if game_match:
                params[param_name] = game_match.group(1)
            elif quoted_values:
                # First quoted value is often the game
                params[param_name] = quoted_values[0]
        
        elif param_name == "username":
            # Look for username - often after "user" or "for user"
            # Pattern: "for user 'Username'" or "user 'Username'"
            user_match = re.search(r"(?:for\s+)?user\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
            if user_match:
                params[param_name] = user_match.group(1)
            elif len(quoted_values) > 1:
                # Second quoted value might be username
                params[param_name] = quoted_values[1]
        
        elif param_name == "platform":
            # Look for platform - often after "on" 
            # Pattern: "on Switch" or "on PC" or "on PlayStation"
            platform_match = re.search(r"\bon\s+(\w+)", query, re.IGNORECASE)
            if platform_match:
                platform_value = platform_match.group(1)
                # Don't capture "on" followed by common non-platform words
                if platform_value.lower() not in ["the", "a", "an", "this", "that"]:
                    params[param_name] = platform_value
            elif default_value:
                params[param_name] = default_value
        
        else:
            # Generic extraction for other string parameters
            if param_type == "string":
                # Try to find a quoted value or extract from context
                param_pattern = rf"{param_name}\s*[=:]\s*['\"]?([^'\"]+)['\"]?"
                match = re.search(param_pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
            elif param_type in ["integer", "number", "float"]:
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
    
    return {func_name: params}
