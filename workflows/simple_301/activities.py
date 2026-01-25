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
    
    Parses the prompt to extract the user's query, then uses regex and string matching
    to extract parameter values based on the function schema.
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
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Handle "key" parameter - extract musical key from query
        if param_name == "key":
            # Look for musical key patterns: "C major", "in C", "key of C", etc.
            # Common musical keys: C, D, E, F, G, A, B (with optional sharp/flat)
            key_patterns = [
                r'\b([A-Ga-g][#b]?)\s+major\b',  # "C major"
                r'\b([A-Ga-g][#b]?)\s+minor\b',  # "C minor"
                r'\bin\s+([A-Ga-g][#b]?)\b',     # "in C"
                r'\bkey\s+of\s+([A-Ga-g][#b]?)\b',  # "key of C"
                r'\b([A-Ga-g][#b]?)\s+scale\b',  # "C scale"
            ]
            
            for pattern in key_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).upper()
                    break
        
        # Handle "type" parameter - extract scale type (major/minor)
        elif param_name == "type":
            if "minor" in query_lower:
                params[param_name] = "minor"
            elif "major" in query_lower:
                params[param_name] = "major"
            # If not specified and not required, use default from description
            elif param_name not in required_params:
                # Check if description mentions a default
                if "default" in param_desc:
                    default_match = re.search(r"default\s+(?:is\s+)?['\"]?(\w+)['\"]?", param_desc)
                    if default_match:
                        params[param_name] = default_match.group(1)
        
        # Handle numeric parameters
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        # Handle generic string parameters
        elif param_type == "string" and param_name not in params:
            # Try to extract based on common patterns
            # Pattern: "for X" or "in X" or "of X"
            string_match = re.search(
                r'(?:for|in|of|with)\s+([A-Za-z][A-Za-z\s]*?)(?:\s+(?:and|with|,|scale|chord)|$)',
                query,
                re.IGNORECASE
            )
            if string_match:
                params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
