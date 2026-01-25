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
    """Extract function name and parameters from user query using regex/parsing.
    
    Returns format: {"function_name": {"param1": val1, ...}}
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
    
    # Extract parameters using regex based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract integers from query
            # Try patterns like "number X", "of X", or just standalone numbers
            patterns = [
                r'(?:number|of|factor(?:s)?)\s+(\d+)',
                r'(\d+)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, query, re.IGNORECASE)
                if matches:
                    # Take the largest number found (likely the target number)
                    numbers = [int(m) for m in matches]
                    params[param_name] = max(numbers)
                    break
        
        elif param_type == "number" or param_type == "float":
            # Extract floats/numbers
            patterns = [
                r'(\d+\.?\d*)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, query)
                if matches:
                    params[param_name] = float(matches[0])
                    break
        
        elif param_type == "string":
            # Extract string values - look for quoted strings or named entities
            # Pattern: "for X" or "in X" or after common prepositions
            patterns = [
                r'"([^"]+)"',  # Quoted strings
                r"'([^']+)'",  # Single quoted
                r'(?:for|in|of|with|named?)\s+([A-Za-z][A-Za-z\s]+?)(?:\s*[,.]|$)',
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    return {func_name: params}
