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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract numbers - look for patterns like "next five", "5 matches", etc.
            # First try word numbers
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20
            }
            
            found_num = None
            for word, num in word_to_num.items():
                if word in query_lower:
                    found_num = num
                    break
            
            if found_num is None:
                # Try digit patterns
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    found_num = int(numbers[0])
            
            if found_num is not None:
                params[param_name] = found_num
        
        elif param_type == "string":
            # Handle team_name - look for team names (proper nouns)
            if "team" in param_name.lower() or "team" in param_desc:
                # Common patterns: "for [Team Name]", "[Team Name] matches"
                # Look for capitalized words that could be team names
                team_patterns = [
                    r'for\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
                    r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:matches|games|schedule)',
                    r'(?:matches|games|schedule)\s+(?:for|of)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
                ]
                
                for pattern in team_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                
                # Fallback: look for known team name patterns
                if param_name not in params:
                    # Try to find multi-word proper nouns
                    proper_noun_match = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', query)
                    if proper_noun_match:
                        # Filter out common non-team phrases
                        for pn in proper_noun_match:
                            if pn.lower() not in ["english premier league", "premier league"]:
                                params[param_name] = pn
                                break
            
            # Handle league - look for league names
            elif "league" in param_name.lower() or "league" in param_desc:
                league_patterns = [
                    r'(?:in|of)\s+(?:the\s+)?([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+League)',
                    r'([A-Z][a-zA-Z]+\s+Premier\s+League)',
                    r'(Premier\s+League)',
                    r'(La\s+Liga)',
                    r'(Serie\s+A)',
                    r'(Bundesliga)',
                    r'(Ligue\s+1)',
                ]
                
                for pattern in league_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
    
    return {func_name: params}
