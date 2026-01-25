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
    
    Uses regex and string matching to extract values - no LLM calls needed.
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
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "team":
            # Extract team name - look for known patterns
            # Pattern: "ranking of X" or "X's ranking" or "X in the"
            team_patterns = [
                r'ranking of\s+([A-Za-z\s]+?)(?:\s+in\s+the|\s+in\s+\d)',
                r"([A-Za-z\s]+?)'s\s+ranking",
                r'of\s+([A-Za-z\s]+?)\s+in\s+the',
            ]
            for pattern in team_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
        
        elif param_name == "league":
            # Extract league name - look for known league patterns
            league_patterns = [
                r'(\d{4})\s+([A-Za-z\s]+?)\s+season',
                r'in\s+the\s+\d{4}\s+([A-Za-z\s]+?)\s+season',
                r'the\s+(\d{4})\s+([A-Za-z\s]+)',
            ]
            for pattern in league_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    # Get the league part (last group before "season")
                    groups = match.groups()
                    for g in groups:
                        if g and not g.isdigit():
                            params[param_name] = g.strip()
                            break
                    if param_name in params:
                        break
        
        elif param_name == "season":
            # Extract season/year - look for 4-digit year
            year_match = re.search(r'\b(20\d{2})\b', query)
            if year_match:
                params[param_name] = year_match.group(1)
    
    return {func_name: params}
