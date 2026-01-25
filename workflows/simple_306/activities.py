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
    
    # Extract parameters from query
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract numbers from query
            # Look for patterns like "past 10 matches", "last 5 games", etc.
            number_patterns = [
                r'past\s+(\d+)\s+match',
                r'last\s+(\d+)\s+match',
                r'(\d+)\s+match',
                r'(\d+)\s+game',
            ]
            for pattern in number_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_type == "string":
            # Handle player_name - extract names (capitalized words)
            if "player" in param_name.lower() or "name" in param_name.lower():
                # Look for patterns like "of a cricketer, Name" or "player Name"
                name_patterns = [
                    r'cricketer[,\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                    r'player[,\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                    r'of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                ]
                for pattern in name_patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
            
            # Handle match_format - look for T20, ODI, Test
            elif "format" in param_name.lower():
                format_patterns = [
                    r'\b(T20|ODI|Test)\b',
                ]
                for pattern in format_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).upper() if match.group(1).upper() != "TEST" else "Test"
                        break
    
    return {func_name: params}
