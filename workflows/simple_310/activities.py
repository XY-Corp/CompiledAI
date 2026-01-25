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
    
    Uses regex and string parsing to extract values - no LLM calls needed.
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
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # For player_name - extract the name from the query
        if "player" in param_name.lower() and "name" in param_name.lower():
            # Pattern: "player [Name]" or "of [Name]" or just look for capitalized names
            # Common patterns: "career stats of LeBron James", "player LeBron James"
            name_patterns = [
                r'(?:player|of|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # "of LeBron James"
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\?|$|\s+career|\s+stats)',  # "LeBron James?"
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
            
            # Fallback: look for any sequence of capitalized words (likely a name)
            if param_name not in params:
                # Find capitalized word sequences that look like names
                name_match = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', query)
                if name_match:
                    # Filter out common non-name words
                    for potential_name in name_match:
                        if potential_name.lower() not in ['what', 'the', 'career', 'stats']:
                            params[param_name] = potential_name
                            break
        
        # For team - extract team name if mentioned
        elif "team" in param_name.lower():
            # Look for team patterns: "for [Team]", "on [Team]", "with [Team]"
            team_patterns = [
                r'(?:for|on|with|plays for|played for)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'(?:team|Team)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            ]
            
            for pattern in team_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
            # Team is optional, so don't add if not found
        
        # For numeric parameters
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        # For generic string parameters - try to extract based on description
        elif param_type == "string" and param_name not in params:
            # Only add if it's required and we haven't found it yet
            if param_name in required_params:
                # Try to extract any quoted strings
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
    
    return {func_name: params}
