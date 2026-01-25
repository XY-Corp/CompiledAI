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
        
        if param_type == "integer":
            # Extract year or other integers using regex
            # Look for 4-digit years first
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
            if year_match:
                params[param_name] = int(year_match.group(1))
            else:
                # Fallback to any number
                numbers = re.findall(r'\b\d+\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Handle player_name - extract name patterns
            if "player" in param_name.lower() or "name" in param_name.lower():
                # Common patterns: "of X's", "X's matches", "statistics of X"
                name_patterns = [
                    r"(?:of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'s",  # "of Ronaldo's"
                    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'s\s+(?:matches|statistics|stats)",  # "Ronaldo's matches"
                    r"(?:player|about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",  # "player Ronaldo"
                    r"statistics\s+(?:of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",  # "statistics of Ronaldo"
                ]
                
                for pattern in name_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                
                # Fallback: find capitalized words that look like names
                if param_name not in params:
                    # Look for capitalized words (potential names)
                    name_candidates = re.findall(r'\b([A-Z][a-z]+)\b', query)
                    # Filter out common words
                    common_words = {'What', 'The', 'How', 'When', 'Where', 'Who', 'Which', 'Year'}
                    names = [n for n in name_candidates if n not in common_words]
                    if names:
                        params[param_name] = names[0]
            
            # Handle team_name - only if explicitly mentioned
            elif "team" in param_name.lower():
                team_patterns = [
                    r"(?:team|club)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                    r"(?:for|at|with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:team|club)",
                ]
                for pattern in team_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
                # Don't add team_name if not found (it's optional)
    
    return {func_name: params}
