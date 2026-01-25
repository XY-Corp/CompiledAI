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
        param_desc = param_info.get("description", "").lower()
        
        # Extract location (city and state)
        if param_name == "location" or "city" in param_desc or "location" in param_desc:
            # Common patterns for location extraction
            location_patterns = [
                r'(?:in|near|at|around|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "in Seattle" or "in New York"
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s*(?:[A-Z]{2})?',  # "Seattle, WA" or "Seattle"
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, query)
                if match:
                    location = match.group(1).strip()
                    # Check if it's a known city (not a common word)
                    common_words = {'find', 'get', 'show', 'list', 'search', 'me', 'that', 'plays', 'music'}
                    if location.lower() not in common_words:
                        params[param_name] = location
                        break
        
        # Extract genre (music type)
        elif param_name == "genre" or "genre" in param_desc or "music" in param_desc:
            # Common music genres
            genres = [
                'jazz', 'rock', 'pop', 'classical', 'hip hop', 'hip-hop', 'country',
                'blues', 'r&b', 'electronic', 'metal', 'folk', 'indie', 'punk',
                'soul', 'reggae', 'latin', 'alternative', 'edm', 'techno', 'house'
            ]
            
            query_lower = query.lower()
            for genre in genres:
                if genre in query_lower:
                    params[param_name] = genre
                    break
        
        # Generic string extraction for other parameters
        elif param_type == "string":
            # Try to extract quoted strings first
            quoted_match = re.search(r'"([^"]+)"', query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
        
        # Extract numbers for numeric parameters
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
