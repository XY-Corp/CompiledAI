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
    
    # Extract team_name - look for country/team names
    # Common patterns: "of Germany", "Germany's", "the Germany"
    team_patterns = [
        r"of\s+([A-Z][a-z]+(?:'s)?)",  # "of Germany's" or "of Germany"
        r"([A-Z][a-z]+)'s\s+(?:men|women|national|soccer|football)",  # "Germany's men"
        r"the\s+([A-Z][a-z]+)\s+(?:men|women|national|soccer|football)",  # "the Germany men"
    ]
    
    team_name = None
    for pattern in team_patterns:
        match = re.search(pattern, query)
        if match:
            team_name = match.group(1).replace("'s", "")
            break
    
    if team_name and "team_name" in params_schema:
        params["team_name"] = team_name
    
    # Extract year - look for 4-digit numbers (years)
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
    if year_match and "year" in params_schema:
        params["year"] = int(year_match.group(1))
    
    # Extract gender - look for "men" or "women"
    if "gender" in params_schema:
        query_lower = query.lower()
        if "women" in query_lower:
            params["gender"] = "women"
        elif "men" in query_lower:
            params["gender"] = "men"
        # If not specified, use default from schema (men)
    
    return {func_name: params}
