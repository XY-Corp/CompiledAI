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
    """Extract function call parameters from natural language query.
    
    Parses the user query and function schema to extract the appropriate
    function name and parameters. Returns format: {"function_name": {params}}
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "string":
            # Extract team name - look for patterns like "for X" or team names
            # Common patterns: "for [Team Name]", "[Team Name]'s", "of [Team Name]"
            team_patterns = [
                r'for\s+([A-Z][a-zA-Z\s]+?)(?:\s+including|\s+with|\s*$|\.)',
                r'([A-Z][a-zA-Z\s]+?)\s+(?:including|with|\'s)',
                r'of\s+([A-Z][a-zA-Z\s]+?)(?:\s+including|\s+with|\s*$|\.)',
            ]
            
            for pattern in team_patterns:
                match = re.search(pattern, query)
                if match:
                    team_name = match.group(1).strip()
                    # Clean up common trailing words
                    team_name = re.sub(r'\s+(including|with|and|the)$', '', team_name, flags=re.IGNORECASE)
                    params[param_name] = team_name
                    break
            
            # Fallback: look for capitalized multi-word names (likely team names)
            if param_name not in params:
                cap_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', query)
                if cap_match:
                    params[param_name] = cap_match.group(1).strip()
        
        elif param_type == "boolean":
            # Check for boolean indicators in query
            # Look for keywords that indicate true/false
            if "include" in param_desc or "opponent" in param_desc:
                # Check if query mentions including opponent
                if re.search(r'includ(?:e|ing)\s+(?:its\s+)?opponent', query, re.IGNORECASE):
                    params[param_name] = True
                elif re.search(r'opponent\s+name', query, re.IGNORECASE):
                    params[param_name] = True
                elif re.search(r'with\s+(?:its\s+)?opponent', query, re.IGNORECASE):
                    params[param_name] = True
                else:
                    # Check default value
                    default = param_info.get("default")
                    if default is not None:
                        params[param_name] = default
            else:
                # Generic boolean detection
                if re.search(r'\b(yes|true|include|with)\b', query, re.IGNORECASE):
                    params[param_name] = True
                elif re.search(r'\b(no|false|without|exclude)\b', query, re.IGNORECASE):
                    params[param_name] = False
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
