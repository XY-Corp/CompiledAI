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
    
    # For get_collectables_in_season, extract game_name and season
    
    # Extract game name - look for quoted game names or common patterns
    # Pattern: 'Game Name' or "Game Name" or "from the game X"
    game_patterns = [
        r"game\s+['\"]([^'\"]+)['\"]",  # game 'Name' or game "Name"
        r"from\s+(?:the\s+)?game\s+['\"]([^'\"]+)['\"]",  # from the game 'Name'
        r"['\"]([^'\"]+)['\"]",  # Any quoted string (likely game name)
        r"from\s+(?:the\s+)?game\s+([A-Z][A-Za-z0-9:\s\-']+?)(?:\s+during|\s+in|\s+for|$)",  # from the game Name
    ]
    
    game_name = None
    for pattern in game_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            game_name = match.group(1).strip()
            break
    
    # Extract season - look for season names
    season_patterns = [
        r"(?:during|in|for)\s+(?:the\s+)?(\w+)\s+season",  # during the Spring season
        r"(\w+)\s+season",  # Spring season
        r"(?:during|in|for)\s+(Spring|Summer|Fall|Autumn|Winter)",  # during Spring
    ]
    
    season = None
    for pattern in season_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            season = match.group(1).strip()
            # Capitalize first letter
            season = season.capitalize()
            break
    
    # Extract item_type if mentioned (optional parameter)
    item_type_patterns = [
        r"(?:all|only)\s+(bug|fish|sea\s+creature)s?",  # all bugs, only fish
        r"(bug|fish|sea\s+creature)s?\s+(?:items?|collectables?)",  # bug items
    ]
    
    item_type = None
    for pattern in item_type_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            item_type = match.group(1).strip().lower()
            if item_type == "sea creature":
                item_type = "sea creatures"
            break
    
    # Build params dict with required parameters
    if "game_name" in params_schema and game_name:
        params["game_name"] = game_name
    
    if "season" in params_schema and season:
        params["season"] = season
    
    # Only include item_type if explicitly mentioned (it's optional with default 'all')
    if "item_type" in params_schema and item_type:
        params["item_type"] = item_type
    
    return {func_name: params}
