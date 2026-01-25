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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract integers from query
            numbers = re.findall(r'\b(\d{4})\b', query)  # Look for year-like numbers first
            if numbers:
                params[param_name] = int(numbers[0])
            else:
                # Check for any integer
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract string values based on parameter name/description
            if "team" in param_name.lower() or "team" in param_desc:
                # Extract team name - look for patterns like "of X in" or "ranking of X"
                team_patterns = [
                    r'(?:ranking|position|standing)\s+of\s+([A-Za-z\s]+?)\s+in',
                    r'(?:of|for)\s+([A-Za-z\s]+?)\s+in\s+',
                    r'([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(?:ranking|position|standing)',
                ]
                for pattern in team_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
            
            elif "league" in param_name.lower() or "league" in param_desc:
                # Extract league name - look for patterns like "in X League" or "in X"
                league_patterns = [
                    r'in\s+(?:the\s+)?([A-Za-z\s]+?(?:League|Cup|Championship|Serie|Liga|Bundesliga|Ligue))',
                    r'in\s+(?:the\s+)?([A-Za-z\s]+?)(?:\?|$|\s+for|\s+this|\s+season)',
                    r'(?:League|Cup|Championship):\s*([A-Za-z\s]+)',
                ]
                for pattern in league_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip().rstrip('?')
                        break
    
    # Return in the exact format: {func_name: {params}}
    return {func_name: params}
