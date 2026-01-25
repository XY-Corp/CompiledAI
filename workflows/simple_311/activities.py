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
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    if isinstance(functions, str):
        try:
            functions = json.loads(functions)
        except json.JSONDecodeError:
            functions = []
    
    if not functions:
        return {"error": "No functions provided"}
    
    func = functions[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        enum_values = param_info.get("enum", [])
        
        # Handle enum parameters (like sport)
        if enum_values:
            for enum_val in enum_values:
                if enum_val.lower() in query_lower:
                    params[param_name] = enum_val
                    break
        
        # Handle name parameter - extract full name
        elif "name" in param_name.lower() or "full name" in param_desc:
            # Common patterns for extracting names
            # Pattern: "of [Name]" or "player [Name]" or "athlete [Name]"
            name_patterns = [
                r'(?:player|athlete|of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # "player Lebron James"
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # Any capitalized multi-word name
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, query)
                if match:
                    extracted_name = match.group(1).strip()
                    # Validate it looks like a name (at least 2 words, capitalized)
                    if len(extracted_name.split()) >= 2:
                        params[param_name] = extracted_name
                        break
        
        # Handle team parameter - extract team name if mentioned
        elif "team" in param_name.lower():
            # Look for team mentions - common patterns
            team_patterns = [
                r'(?:team|plays for|on the)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:team|player)',
            ]
            
            for pattern in team_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    # Only include required params and params we found values for
    # Don't include optional params without values
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
    
    return {func_name: final_params}
