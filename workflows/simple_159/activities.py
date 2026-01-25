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
    """Extract function name and parameters from user query using regex and string parsing."""
    
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
            # Extract year - look for 4-digit numbers (years)
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
            if year_match:
                params[param_name] = int(year_match.group(1))
        
        elif param_type == "string":
            # For act_name, extract the act name from the query
            # Pattern: "details of X" or "about X" where X is the act name
            # Common patterns: "Criminal Law Amendment Act", "Right to Information Act", etc.
            
            # Try to extract act name - look for patterns like "X Act" or "X Bill"
            # Pattern 1: "details of <Act Name> of <year>" or "details of <Act Name>"
            act_patterns = [
                r'details?\s+of\s+(?:the\s+)?(.+?(?:Act|Bill|Code|Law|Amendment)(?:\s+Act)?)\s+of\s+\d{4}',
                r'details?\s+of\s+(?:the\s+)?(.+?(?:Act|Bill|Code|Law|Amendment)(?:\s+Act)?)',
                r'about\s+(?:the\s+)?(.+?(?:Act|Bill|Code|Law|Amendment)(?:\s+Act)?)',
                r'(?:the\s+)?(.+?(?:Act|Bill|Code|Law|Amendment)(?:\s+Act)?)\s+of\s+\d{4}',
            ]
            
            for pattern in act_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    act_name = match.group(1).strip()
                    # Clean up: remove trailing "of" if present
                    act_name = re.sub(r'\s+of\s*$', '', act_name, flags=re.IGNORECASE)
                    params[param_name] = act_name
                    break
    
    return {func_name: params}
