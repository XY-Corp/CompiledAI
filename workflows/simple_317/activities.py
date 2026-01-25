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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract team_name - look for team names (LA Lakers, etc.)
    team_patterns = [
        r'\b(LA Lakers|Los Angeles Lakers|Lakers)\b',
        r'\b(Golden State Warriors|Warriors)\b',
        r'\b(Boston Celtics|Celtics)\b',
        r'\b(Miami Heat|Heat)\b',
        r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:s)?)\b',  # Generic team pattern
    ]
    
    team_name = None
    for pattern in team_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            team_name = match.group(1)
            # Normalize common team names
            if team_name.lower() in ['la lakers', 'lakers', 'los angeles lakers']:
                team_name = "LA Lakers"
            break
    
    if team_name:
        params["team_name"] = team_name
    
    # Extract league - look for league names
    league_patterns = [
        (r'\bNBA\b', "NBA"),
        (r'\bNFL\b', "NFL"),
        (r'\bMLB\b', "MLB"),
        (r'\bNHL\b', "NHL"),
        (r'\bMLS\b', "MLS"),
    ]
    
    for pattern, league_value in league_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            params["league"] = league_value
            break
    
    # Extract season - look for year patterns
    season_match = re.search(r'\b(20\d{2}(?:-\d{2,4})?|\d{4})\b', query)
    if season_match:
        params["season"] = season_match.group(1)
    
    # Extract type - regular or playoff
    if 'playoff' in query_lower:
        params["type"] = "playoff"
    elif 'regular' in query_lower:
        params["type"] = "regular"
    
    return {func_name: params}
