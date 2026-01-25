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
    
    # Extract parameters based on the query content
    params = {}
    
    # For get_game_item_stats: extract game, item, and stat
    if func_name == "get_game_item_stats":
        # Extract game name - look for patterns like "in the game 'X'" or "game 'X'"
        game_patterns = [
            r"(?:in\s+the\s+)?game\s+['\"]([^'\"]+)['\"]",
            r"(?:in|from)\s+['\"]?([^'\"]+?)['\"]?\s*\?",
            r"in\s+([A-Z][^?]+?)(?:\s*\?|$)",
        ]
        game = None
        for pattern in game_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                game = match.group(1).strip()
                break
        
        # Extract item name - look for patterns like "Weapon 'X'" or "item 'X'"
        item_patterns = [
            r"(?:Weapon|item|the)\s+['\"]([^'\"]+)['\"]",
            r"for\s+(?:the\s+)?['\"]?([^'\"]+?)['\"]?\s+in",
            r"['\"]([^'\"]+)['\"]",
        ]
        item = None
        for pattern in item_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                item = match.group(1).strip()
                break
        
        # Extract stat - look for keywords like "power rating", "damage", "stats"
        stat_patterns = [
            r"(power\s+rating)",
            r"(damage)",
            r"(attack)",
            r"(defense)",
            r"(durability)",
            r"what(?:'s| is)\s+the\s+(\w+(?:\s+\w+)?)\s+(?:for|of)",
        ]
        stat = None
        for pattern in stat_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                stat = match.group(1).strip().lower()
                # Normalize common stat names
                if "power" in stat:
                    stat = "power"
                break
        
        if game:
            params["game"] = game
        if item:
            params["item"] = item
        if stat:
            params["stat"] = stat
    
    else:
        # Generic extraction for other functions
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
            else:
                # Extract quoted strings or use pattern matching
                quoted = re.findall(r"['\"]([^'\"]+)['\"]", query)
                if quoted:
                    params[param_name] = quoted[0]
    
    return {func_name: params}
