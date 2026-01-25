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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question = data["question"]
            if isinstance(question, list) and len(question) > 0:
                if isinstance(question[0], list) and len(question[0]) > 0:
                    query = question[0][0].get("content", str(prompt))
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    # Extract player_name - look for quoted name or common patterns
    # Pattern: 'Name' or "Name" or "player Name"
    player_match = re.search(r"['\"]([A-Z][a-z]+ [A-Z][a-z]+)['\"]", query)
    if player_match:
        params["player_name"] = player_match.group(1)
    else:
        # Try pattern: "player X" or "for X"
        player_match = re.search(r"(?:player|for)\s+([A-Z][a-z]+ [A-Z][a-z]+)", query)
        if player_match:
            params["player_name"] = player_match.group(1)
    
    # Extract metrics - look for specific stat keywords
    metrics_enum = ["Points", "Rebounds", "Assists", "Blocks"]
    found_metrics = []
    
    # Check for each metric (case-insensitive)
    metric_patterns = {
        "point": "Points",
        "rebound": "Rebounds", 
        "assist": "Assists",
        "block": "Blocks"
    }
    
    for pattern, metric in metric_patterns.items():
        if pattern in query_lower:
            found_metrics.append(metric)
    
    if found_metrics:
        params["metrics"] = found_metrics
    
    # Extract team if mentioned (optional parameter)
    # Common NBA team patterns
    team_match = re.search(r"(?:from|for|on|plays for)\s+(?:the\s+)?([A-Z][a-z]+(?: [A-Z][a-z]+)*)", query)
    if team_match:
        potential_team = team_match.group(1)
        # Filter out non-team words
        if potential_team.lower() not in ["last", "basketball", "game", "stats"]:
            params["team"] = potential_team
    
    # For required params without values, use <UNKNOWN>
    for req_param in required_params:
        if req_param not in params:
            params[req_param] = "<UNKNOWN>"
    
    return {func_name: params}
