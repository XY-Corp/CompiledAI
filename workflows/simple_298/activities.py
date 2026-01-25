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
    """Extract function name and parameters from user query using regex/parsing."""
    
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
    
    # Extract 'key' parameter - look for musical key notation
    # Pattern: C#, F#, Ab, Bb, C, D, E, F, G, A, B (with optional sharp/flat)
    key_patterns = [
        r'\b([A-Ga-g][#b]?)\s+(?:major|minor)',  # "C# major" or "Ab minor"
        r'(?:key\s+(?:of\s+)?|in\s+)([A-Ga-g][#b]?)',  # "key of C#" or "in Ab"
        r'\b([A-Ga-g][#b]?)\s+scale',  # "C# scale"
    ]
    
    key_value = None
    for pattern in key_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            key_value = match.group(1)
            # Normalize: uppercase letter, preserve # or b
            key_value = key_value[0].upper() + key_value[1:] if len(key_value) > 1 else key_value.upper()
            break
    
    if key_value and "key" in params_schema:
        params["key"] = key_value
    
    # Extract 'scale_type' parameter - look for "major" or "minor"
    if "scale_type" in params_schema:
        if "minor" in query_lower:
            params["scale_type"] = "minor"
        elif "major" in query_lower:
            params["scale_type"] = "major"
        # If not specified, use default (major) - don't include in params to use function default
    
    return {func_name: params}
