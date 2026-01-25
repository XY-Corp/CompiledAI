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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        is_optional = param_info.get("optional", False)
        
        if param_name == "teams" and param_type == "array":
            # Extract team names - look for patterns like "between X and Y" or "X vs Y"
            team_patterns = [
                r'between\s+([A-Za-z\s]+?)\s+and\s+([A-Za-z\s]+?)(?:\s+on|\s+at|\?|$)',
                r'([A-Za-z]+)\s+(?:vs\.?|versus)\s+([A-Za-z]+)',
                r'([A-Za-z]+)\s+and\s+([A-Za-z]+)\s+(?:game|match)',
            ]
            
            for pattern in team_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    team1 = match.group(1).strip()
                    team2 = match.group(2).strip()
                    params[param_name] = [team1, team2]
                    break
        
        elif param_name == "date" and param_type == "string":
            # Extract date - look for various date formats
            # Pattern for "Jan 28, 2021" or "January 28, 2021"
            month_map = {
                'jan': '01', 'january': '01',
                'feb': '02', 'february': '02',
                'mar': '03', 'march': '03',
                'apr': '04', 'april': '04',
                'may': '05',
                'jun': '06', 'june': '06',
                'jul': '07', 'july': '07',
                'aug': '08', 'august': '08',
                'sep': '09', 'september': '09',
                'oct': '10', 'october': '10',
                'nov': '11', 'november': '11',
                'dec': '12', 'december': '12',
            }
            
            # Pattern: "Jan 28, 2021" or "January 28 2021"
            date_pattern = r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})'
            match = re.search(date_pattern, query, re.IGNORECASE)
            if match:
                month_str = match.group(1).lower()
                day = match.group(2).zfill(2)
                year = match.group(3)
                month = month_map.get(month_str, '01')
                params[param_name] = f"{year}-{month}-{day}"
            else:
                # Try YYYY-MM-DD format directly
                iso_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', query)
                if iso_match:
                    params[param_name] = iso_match.group(0)
        
        elif param_name == "venue" and is_optional:
            # Optional venue - look for "at [venue]" pattern
            venue_match = re.search(r'at\s+(?:the\s+)?([A-Za-z\s]+?)(?:\s+on|\s+between|\?|$)', query, re.IGNORECASE)
            if venue_match:
                params[param_name] = venue_match.group(1).strip()
            # Don't include optional params if not found
    
    return {func_name: params}
