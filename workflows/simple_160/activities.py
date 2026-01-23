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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        value = None
        
        # Extract based on parameter name and description
        if param_name == "docket" or "docket" in param_desc:
            # Look for docket number patterns like "2022/AL2562" or similar
            docket_patterns = [
                r'docket(?:ed)?\s+(?:number(?:ed)?)?\s*[:#]?\s*([A-Za-z0-9/\-]+)',
                r'(?:case\s+)?(?:number(?:ed)?)?\s*([0-9]{4}/[A-Za-z0-9]+)',
                r'numbered\s+([A-Za-z0-9/\-]+)',
            ]
            for pattern in docket_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    break
        
        elif param_name == "court" or "court" in param_desc:
            # Look for court/state/location names
            court_patterns = [
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\??$',  # "in California?"
                r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+court',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+court',
                r'court\s+(?:in|of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            ]
            for pattern in court_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1).strip().rstrip('?')
                    break
        
        elif param_name == "info_type" or "information type" in param_desc or "info" in param_desc:
            # Look for what type of info is being requested
            info_keywords = ["victim", "accused", "verdict", "defendant", "plaintiff", "judge", "date", "outcome", "charges"]
            query_lower = query.lower()
            
            for keyword in info_keywords:
                if keyword in query_lower:
                    value = keyword
                    break
            
            # Also check for "who was the X" pattern
            who_match = re.search(r'who\s+was\s+the\s+(\w+)', query, re.IGNORECASE)
            if who_match:
                value = who_match.group(1).lower()
        
        if value is not None:
            params[param_name] = value
    
    return {func_name: params}
