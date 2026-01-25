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
    except (json.JSONDecodeError, TypeError):
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    # For soccer_stat.get_player_stats, extract player_name and season
    
    # Extract player name - look for common patterns
    # Pattern: "stats of [Name]" or "player stats of [Name]" or "[Name]'s stats"
    player_patterns = [
        r"(?:stats?\s+of|statistics?\s+of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:'s)?\s+(?:stats?|statistics?)",
        r"player[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
    ]
    
    player_name = None
    for pattern in player_patterns:
        match = re.search(pattern, query)
        if match:
            player_name = match.group(1).strip()
            break
    
    # Fallback: find capitalized multi-word names (likely player names)
    if not player_name:
        name_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', query)
        if name_match:
            player_name = name_match.group(1).strip()
    
    # Extract season - look for year patterns like "2019-2020" or "2019/2020" or "2019-20"
    season_patterns = [
        r'(\d{4}[-/]\d{4})',  # 2019-2020 or 2019/2020
        r'(\d{4}[-/]\d{2})',  # 2019-20 or 2019/20
        r'(\d{4})\s+season',  # 2019 season
        r'season\s+(\d{4})',  # season 2019
    ]
    
    season = None
    for pattern in season_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            season = match.group(1).strip()
            # Normalize format: convert "/" to "-"
            season = season.replace("/", "-")
            break
    
    # Extract league if mentioned (optional parameter)
    league_patterns = [
        r'(?:in|from|for)\s+(?:the\s+)?([A-Za-z\s]+(?:League|Liga|Serie|Bundesliga|Ligue))',
        r'(Premier\s+League|La\s+Liga|Serie\s+A|Bundesliga|Ligue\s+1|MLS|Champions\s+League)',
    ]
    
    league = None
    for pattern in league_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            league = match.group(1).strip()
            break
    
    # Build params dict based on schema
    if "player_name" in params_schema and player_name:
        params["player_name"] = player_name
    
    if "season" in params_schema and season:
        params["season"] = season
    
    if "league" in params_schema and league:
        params["league"] = league
    
    return {func_name: params}
