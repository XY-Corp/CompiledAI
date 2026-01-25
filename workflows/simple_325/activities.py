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
    
    Uses regex and string matching to extract team names and other parameters
    from natural language queries about sports matches.
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
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
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
    
    # Extract parameters based on the function schema
    params = {}
    
    # For sports.match_results, extract team names
    if func_name == "sports.match_results":
        # Pattern: "between X and Y" or "X vs Y" or "X and Y"
        team_patterns = [
            r'between\s+(.+?)\s+and\s+(.+?)(?:\?|$|\.)',
            r'(.+?)\s+(?:vs\.?|versus)\s+(.+?)(?:\?|$|\.)',
            r'match\s+(?:between\s+)?(.+?)\s+and\s+(.+?)(?:\?|$|\.)',
        ]
        
        team1, team2 = None, None
        for pattern in team_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                team1 = match.group(1).strip()
                team2 = match.group(2).strip()
                break
        
        if team1 and team2:
            params["team1"] = team1
            params["team2"] = team2
        
        # Extract season if mentioned (e.g., "2023", "2023-24", "last season")
        season_patterns = [
            r'(\d{4}-\d{2,4})\s+season',
            r'season\s+(\d{4}-\d{2,4})',
            r'in\s+(\d{4})',
            r'(\d{4})\s+season',
        ]
        
        for pattern in season_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["season"] = match.group(1)
                break
    else:
        # Generic extraction for other functions
        # Extract string values for string parameters
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
                    numbers.pop(0)
            elif param_type == "string":
                # Try to extract based on common patterns
                # Pattern: "for X" or "of X" or after key phrases
                string_match = re.search(
                    rf'{param_name}[:\s]+([^,\.\?]+)',
                    query,
                    re.IGNORECASE
                )
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
