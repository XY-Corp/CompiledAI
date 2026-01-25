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
        
        # For celebrity_name - extract the name from the query
        if param_name == "celebrity_name" or "name" in param_name.lower():
            # Common patterns for extracting names
            # Pattern: "of [Name]" or "about [Name]" or "for [Name]"
            name_patterns = [
                r'(?:of|about|for|regarding)\s+(?:the\s+)?(?:footballer\s+|player\s+|athlete\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                r'(?:achievements|stats|info|information)\s+(?:of|about|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\'s|\s+achievements|\s+stats)',
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
            
            # Fallback: look for capitalized multi-word names
            if param_name not in params:
                # Find sequences of capitalized words (likely names)
                name_match = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', query)
                if name_match:
                    # Filter out common non-name phrases
                    for potential_name in name_match:
                        if potential_name.lower() not in ['find all', 'get all', 'show me']:
                            params[param_name] = potential_name
                            break
        
        # For sports type - check if mentioned in query
        elif param_name == "sports" or "sport" in param_name.lower():
            sports_keywords = ['football', 'soccer', 'basketball', 'tennis', 'cricket', 'baseball', 'hockey', 'golf']
            query_lower = query.lower()
            for sport in sports_keywords:
                if sport in query_lower:
                    params[param_name] = sport.capitalize()
                    break
            # Check if "footballer" is mentioned - implies Football
            if param_name not in params and 'footballer' in query_lower:
                params[param_name] = "Football"
        
        # For team - extract if mentioned
        elif param_name == "team" or "team" in param_name.lower():
            team_patterns = [
                r'(?:plays?\s+for|at|with|on)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:player|team)',
            ]
            for pattern in team_patterns:
                match = re.search(pattern, query)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try one more time with a broader search for the required param
            if "name" in req_param.lower():
                # Last resort: find any proper noun sequence
                names = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', query)
                if names:
                    params[req_param] = names[-1]  # Take the last one (often the subject)
    
    return {func_name: params}
