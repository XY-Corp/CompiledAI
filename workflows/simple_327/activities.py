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
    """Extract function call parameters from user query using regex and string matching."""
    
    # Parse prompt - may be JSON string
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from nested structure
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    # Extract team_name - look for team names
    team_patterns = [
        r'schedule of ([A-Z][a-zA-Z\s]+?)(?:\s+for|\s+in|\s+next)',
        r'([A-Z][a-zA-Z\s]+?)(?:\'s|s\')\s+schedule',
        r'for\s+([A-Z][a-zA-Z\s]+?)(?:\s+in|\s+for|\s+next)',
    ]
    
    for pattern in team_patterns:
        match = re.search(pattern, query)
        if match:
            params["team_name"] = match.group(1).strip()
            break
    
    # Fallback: look for known team names
    if "team_name" not in params:
        known_teams = ["Manchester United", "Manchester City", "Liverpool", "Chelsea", "Arsenal"]
        for team in known_teams:
            if team.lower() in query_lower:
                params["team_name"] = team
                break
    
    # Extract num_of_games - look for numbers
    num_patterns = [
        r'next\s+(\d+)\s+games',
        r'(\d+)\s+games',
        r'(\d+)\s+matches',
        r'next\s+(\d+)',
    ]
    
    for pattern in num_patterns:
        match = re.search(pattern, query_lower)
        if match:
            params["num_of_games"] = int(match.group(1))
            break
    
    # Extract league - look for league names
    league_patterns = [
        r'in\s+(?:the\s+)?([A-Z][a-zA-Z\s]+?(?:League|Cup|Championship))',
        r'in\s+(?:the\s+)?([A-Z][a-zA-Z\s]+?)(?:\.|$)',
    ]
    
    for pattern in league_patterns:
        match = re.search(pattern, query)
        if match:
            params["league"] = match.group(1).strip().rstrip('.')
            break
    
    # Fallback: look for known leagues
    if "league" not in params:
        known_leagues = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Champions League"]
        for league in known_leagues:
            if league.lower() in query_lower:
                params["league"] = league
                break
    
    # Extract location (optional) - look for city/venue
    location_patterns = [
        r'at\s+([A-Z][a-zA-Z\s]+?)(?:\.|,|$)',
        r'in\s+([A-Z][a-zA-Z]+)\s+(?:stadium|arena)',
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, query)
        if match:
            params["location"] = match.group(1).strip()
            break
    
    return {func_name: params}
