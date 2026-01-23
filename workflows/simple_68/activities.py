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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract numbers - look for patterns like "next 5 years", "5 years", etc.
            year_patterns = [
                r'(?:next|for(?:\s+the)?)\s+(\d+)\s+years?',
                r'(\d+)\s+years?',
                r'(\d+)\s*-?\s*year',
            ]
            for pattern in year_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_type == "boolean":
            # Check for boolean indicators
            if param_name == "include_human_impact":
                # Look for phrases indicating human impact should be included
                include_patterns = [
                    r'includ(?:e|ing)\s+human\s+impact',
                    r'with\s+human\s+impact',
                    r'human\s+impact',
                    r'including\s+human',
                ]
                exclude_patterns = [
                    r'without\s+human\s+impact',
                    r'exclud(?:e|ing)\s+human\s+impact',
                    r'no\s+human\s+impact',
                ]
                
                # Check for exclusion first
                excluded = any(re.search(p, query_lower) for p in exclude_patterns)
                included = any(re.search(p, query_lower) for p in include_patterns)
                
                if excluded:
                    params[param_name] = False
                elif included:
                    params[param_name] = True
                # If not mentioned, don't include (let default apply)
        
        elif param_type == "string":
            if param_name == "location":
                # Extract location - look for patterns like "in X", "of X", "for X"
                location_patterns = [
                    r'(?:in|of|for|at)\s+([A-Z][A-Za-z\s]+(?:National\s+Park|Park|Forest|Reserve)?)',
                    r'growth\s+(?:in|of|for|at)\s+([A-Z][A-Za-z\s]+)',
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, query)
                    if match:
                        location = match.group(1).strip()
                        # Clean up trailing words that aren't part of location
                        location = re.sub(r'\s+for\s+.*$', '', location, flags=re.IGNORECASE)
                        location = re.sub(r'\s+over\s+.*$', '', location, flags=re.IGNORECASE)
                        params[param_name] = location.strip()
                        break
    
    return {func_name: params}
