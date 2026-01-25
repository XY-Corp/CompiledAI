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
    """Extract function name and parameters from user query using regex/parsing.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - handle JSON string or dict
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - handle JSON string or list
    if isinstance(functions, str):
        try:
            funcs = json.loads(functions)
        except json.JSONDecodeError:
            funcs = []
    else:
        funcs = functions if functions else []
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        value = None
        
        # Strategy 1: Look for quoted strings (exact values)
        quoted_matches = re.findall(r"['\"]([^'\"]+)['\"]", query)
        
        # Strategy 2: Look for years (4-digit numbers)
        year_matches = re.findall(r'\b(20\d{2}|19\d{2})\b', query)
        
        # Strategy 3: Look for common patterns based on param name/description
        if param_name == "game" or "game" in param_desc:
            # Look for game name - often in quotes or after "game"
            for quoted in quoted_matches:
                # Check if it looks like a game name (not a year)
                if not re.match(r'^\d{4}$', quoted):
                    value = quoted
                    break
            
            # Fallback: look for "game X" or "of game X"
            if not value:
                game_match = re.search(r"(?:game|of)\s+['\"]?([A-Za-z0-9\s]+?)['\"]?(?:\s+in|\s+for|\s+during|$)", query, re.IGNORECASE)
                if game_match:
                    value = game_match.group(1).strip()
        
        elif param_name == "season" or "season" in param_desc:
            # Look for season - often a year or "YYYY season"
            season_match = re.search(r"(\d{4})\s*season", query, re.IGNORECASE)
            if season_match:
                value = season_match.group(1)
            elif year_matches:
                # Use the year found
                value = year_matches[0]
            else:
                # Check quoted values for year-like strings
                for quoted in quoted_matches:
                    if re.match(r'^\d{4}$', quoted):
                        value = quoted
                        break
        
        elif param_type in ["integer", "number"]:
            # Extract numbers
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                value = int(numbers[0]) if param_type == "integer" else float(numbers[0])
        
        else:
            # Generic string extraction - try quoted values first
            if quoted_matches:
                value = quoted_matches[0]
            else:
                # Try to extract based on common patterns
                pattern = rf"(?:{param_name}|for|of|in)\s+['\"]?([A-Za-z0-9\s]+?)['\"]?(?:\s+in|\s+for|\s+during|,|$)"
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
        
        if value is not None:
            params[param_name] = value
    
    return {func_name: params}
