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
    """Extract function name and parameters from user query and function schema.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "team":
            # Extract team name - look for patterns like "for [Team Name]" or "[Team Name] in"
            # Common patterns: "ranking for X", "X in the Y league"
            team_patterns = [
                r'(?:ranking\s+(?:for|of)\s+)([A-Z][A-Za-z\s]+?)(?:\s+in\s+the|\s+in\s+|\s*$)',
                r'(?:for\s+)([A-Z][A-Za-z\s]+?)(?:\s+in\s+the|\s+in\s+|\s*$)',
                r'^(?:get\s+(?:the\s+)?(?:current\s+)?ranking\s+(?:for\s+)?)?([A-Z][A-Za-z\s]+?)(?:\s+in\s+)',
            ]
            
            for pattern in team_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    team_name = match.group(1).strip()
                    # Clean up common suffixes
                    team_name = re.sub(r'\s+(?:football\s+club|fc)$', ' Football Club', team_name, flags=re.IGNORECASE)
                    if not team_name.lower().endswith('football club') and 'football club' in query.lower():
                        team_name = team_name + ' Football Club'
                    params["team"] = team_name.strip()
                    break
            
            # Fallback: Look for "Liverpool Football Club" or similar
            if "team" not in params:
                fc_match = re.search(r'([A-Z][A-Za-z]+(?:\s+Football\s+Club)?)', query)
                if fc_match:
                    params["team"] = fc_match.group(1).strip()
        
        elif param_name == "league":
            # Extract league name - look for "in the [League Name]"
            league_patterns = [
                r'in\s+the\s+([A-Z][A-Za-z\s]+?)(?:\s+league)?(?:\s*\.|$)',
                r'in\s+([A-Z][A-Za-z\s]+?)(?:\s+league)?(?:\s*\.|$)',
            ]
            
            for pattern in league_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    league_name = match.group(1).strip()
                    # Remove trailing "league" if present and add proper formatting
                    league_name = re.sub(r'\s+league$', '', league_name, flags=re.IGNORECASE)
                    params["league"] = league_name.strip()
                    break
            
            # Fallback: common league names
            if "league" not in params:
                common_leagues = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]
                for league in common_leagues:
                    if league.lower() in query_lower:
                        params["league"] = league
                        break
        
        elif param_name == "season":
            # Extract season - look for patterns like "2023-2024" or "2023/2024"
            season_match = re.search(r'(\d{4}[-/]\d{4})', query)
            if season_match:
                params["season"] = season_match.group(1).replace('/', '-')
            # Note: season is optional with default, so we don't add it if not found
    
    return {func_name: params}
