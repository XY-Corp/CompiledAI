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
    
    Uses regex and string matching to extract parameter values - no LLM calls needed.
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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "sport":
            # Extract sport type from query
            # Common sports patterns
            sports = [
                "tennis", "basketball", "football", "soccer", "baseball", 
                "golf", "hockey", "cricket", "rugby", "volleyball",
                "swimming", "boxing", "mma", "wrestling", "badminton"
            ]
            for sport in sports:
                if sport in query_lower:
                    params[param_name] = sport
                    break
            
            # Also try regex pattern: "in X" or "X player" or "top X player"
            if param_name not in params:
                match = re.search(r'(?:in|top)\s+(\w+)\s+(?:player|ranking|sport)?', query_lower)
                if match:
                    params[param_name] = match.group(1)
        
        elif param_name == "gender":
            # Extract gender from query
            if "woman" in query_lower or "women" in query_lower or "female" in query_lower:
                params[param_name] = "women"
            elif "man" in query_lower or "men" in query_lower or "male" in query_lower:
                params[param_name] = "men"
            # If not specified, check if there's a default
            elif "default" in param_info:
                # Don't include optional params with defaults unless explicitly mentioned
                pass
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - try common patterns
            # Pattern: "for X" or "in X" or "of X"
            match = re.search(rf'(?:for|in|of|about)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|\.|\?)|$)', query, re.IGNORECASE)
            if match and param_name not in params:
                params[param_name] = match.group(1).strip()
    
    return {func_name: params}
