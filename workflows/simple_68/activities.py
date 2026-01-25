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
        
        if param_type == "integer":
            # Extract numbers - look for patterns like "next 5 years", "5 years", etc.
            year_patterns = [
                r'(?:next|for(?:\s+the)?)\s+(\d+)\s+years?',
                r'(\d+)\s+years?',
                r'(\d+)\s*-?\s*year',
            ]
            for pattern in year_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    break
        
        elif param_type == "boolean":
            # Check for boolean indicators in the query
            # Look for "including", "include", "with" for true
            # Look for "excluding", "without", "no" for false
            param_desc = param_info.get("description", "").lower()
            
            # Determine what this boolean is about from description
            if "human" in param_desc or "impact" in param_desc:
                # Check if query mentions human impact
                if re.search(r'\b(?:includ(?:e|ing)|with)\s+human\s+impact', query, re.IGNORECASE):
                    params[param_name] = True
                elif re.search(r'\bhuman\s+impact\b', query, re.IGNORECASE):
                    params[param_name] = True
                elif re.search(r'\b(?:exclud(?:e|ing)|without|no)\s+human', query, re.IGNORECASE):
                    params[param_name] = False
                # If not mentioned and not required, could skip or default
        
        elif param_type == "string":
            # Extract location - look for patterns like "in X", "of X", "for X"
            param_desc = param_info.get("description", "").lower()
            
            if "location" in param_name.lower() or "location" in param_desc:
                # Common location extraction patterns
                location_patterns = [
                    r'(?:in|at|for|of)\s+([A-Z][A-Za-z\s]+(?:National\s+Park|Park|Forest|Reserve)?)',
                    r'(?:growth\s+(?:in|of|at))\s+([A-Z][A-Za-z\s]+)',
                    r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+National\s+Park)',
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, query)
                    if match:
                        location = match.group(1).strip()
                        # Clean up trailing words that aren't part of location
                        location = re.sub(r'\s+for\s+.*$', '', location, flags=re.IGNORECASE)
                        params[param_name] = location
                        break
    
    return {func_name: params}
