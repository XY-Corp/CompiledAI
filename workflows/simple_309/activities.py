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
    
    # Extract parameters from query
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "player_name":
            # Extract player name - look for capitalized names
            # Pattern: "record of [Name]" or "[Name]'s record" or just capitalized words
            name_patterns = [
                r'record of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\'s|\s+in\s+the)',
                r'(?:player|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            ]
            for pattern in name_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "season_year":
            # Extract year - look for 4-digit year, especially near "season"
            year_patterns = [
                r'(\d{4})\s+(?:NFL\s+)?season',
                r'(?:in|for|during)\s+(?:the\s+)?(\d{4})',
                r'(\d{4})',
            ]
            for pattern in year_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    year = int(match.group(1))
                    # Validate it's a reasonable NFL season year
                    if 1920 <= year <= 2030:
                        params[param_name] = year
                        break
        
        elif param_name == "team":
            # Extract team name - look for NFL team patterns
            # Common patterns: "for the [Team]", "with [Team]", "[Team] team"
            team_patterns = [
                r'(?:for|with|on)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+team',
            ]
            for pattern in team_patterns:
                match = re.search(pattern, query)
                if match:
                    potential_team = match.group(1).strip()
                    # Avoid matching player name as team
                    if potential_team != params.get("player_name", ""):
                        params[param_name] = potential_team
                        break
            # Note: team is optional, so we don't add it if not found
    
    return {func_name: params}
