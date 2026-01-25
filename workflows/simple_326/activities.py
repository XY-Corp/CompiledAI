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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
    # Parse prompt (may be JSON string with nested structure)
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
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # Extract team_name - look for team names in the query
            if param_name == "team_name" or "team" in param_name.lower():
                # Common patterns: "for [Team Name]", "[Team Name] in"
                # Look for capitalized words that could be team names
                team_patterns = [
                    r'(?:for|of)\s+([A-Z][a-zA-Z\s]+?)(?:\s+in\s+|\s*$)',
                    r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:in\s+[A-Z])',
                    r'score.*?(?:for|of)\s+([A-Z][a-zA-Z\s]+)',
                ]
                
                for pattern in team_patterns:
                    match = re.search(pattern, query)
                    if match:
                        team = match.group(1).strip()
                        # Clean up - remove trailing "in" if present
                        team = re.sub(r'\s+in\s*$', '', team, flags=re.IGNORECASE).strip()
                        if team:
                            params[param_name] = team
                            break
                
                # Fallback: look for known team name patterns
                if param_name not in params:
                    # Look for "Los Angeles Lakers" pattern
                    match = re.search(r'(Los Angeles Lakers|Los Angeles Clippers|New York Knicks|Boston Celtics|Chicago Bulls|Golden State Warriors|Miami Heat|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+[A-Z][a-z]+)', query)
                    if match:
                        params[param_name] = match.group(1).strip()
            
            # Extract league - look for league names
            elif param_name == "league" or "league" in param_name.lower():
                # Common leagues
                leagues = ["NBA", "NFL", "MLB", "NHL", "MLS", "Premier League", "La Liga", "Bundesliga", "Serie A"]
                for league in leagues:
                    if league.lower() in query_lower or league in query:
                        params[param_name] = league
                        break
                
                # Fallback: regex for "in [LEAGUE]"
                if param_name not in params:
                    match = re.search(r'in\s+([A-Z]{2,}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', query)
                    if match:
                        params[param_name] = match.group(1).strip()
        
        elif param_type == "boolean":
            # Check for boolean indicators in query
            if param_name == "include_player_stats" or "player" in param_name.lower() or "stats" in param_name.lower():
                # Look for mentions of player stats
                if any(kw in query_lower for kw in ["player stat", "individual stat", "player performance", "include player"]):
                    params[param_name] = True
                # Default to True if "statistics" is mentioned (implies detailed stats)
                elif "statistics" in query_lower:
                    params[param_name] = True
                # Otherwise use default (don't include in params, let default apply)
    
    return {func_name: params}
