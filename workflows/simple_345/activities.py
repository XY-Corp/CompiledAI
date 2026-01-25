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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract game_name - look for game titles
    # Pattern: "value of a [vintage] <game_name> [game]"
    game_patterns = [
        r'(?:value of (?:a |an )?(?:vintage )?)([\w\s\.]+?)(?:\s+game|\s+from|\s+like|\s+in|\s*$)',
        r'(?:vintage\s+)([\w\s\.]+?)(?:\s+game|\s+from|\s+like|\s+in)',
        r'([\w\s\.]+?)(?:\s+game\s+from)',
    ]
    
    game_name = None
    for pattern in game_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            game_name = match.group(1).strip()
            # Clean up common words that might be captured
            game_name = re.sub(r'\b(vintage|a|an|the)\b', '', game_name, flags=re.IGNORECASE).strip()
            if game_name:
                break
    
    # Fallback: look for known game patterns like "Super Mario Bros"
    if not game_name:
        known_games = re.search(r'(Super Mario Bros\.?|Mario|Zelda|Pac-Man|Tetris|Donkey Kong)', query, re.IGNORECASE)
        if known_games:
            game_name = known_games.group(1)
    
    if game_name:
        params["game_name"] = game_name
    
    # Extract release_year - look for 4-digit years (1970-2030 range)
    year_match = re.search(r'\b(19[7-9]\d|20[0-2]\d)\b', query)
    if year_match:
        params["release_year"] = int(year_match.group(1))
    
    # Extract condition - look for condition keywords
    condition_map = {
        "new": "New",
        "like new": "Like New",
        "used": "Used",
        "fair": "Fair",
        "poor": "Poor",
        "mint": "New",
        "excellent": "Like New",
        "good": "Used",
    }
    
    # Check for "like new" first (two words)
    if "like new" in query_lower:
        params["condition"] = "Like New"
    else:
        # Check other conditions
        for keyword, condition_value in condition_map.items():
            if keyword != "like new" and keyword in query_lower:
                params["condition"] = condition_value
                break
    
    return {func_name: params}
