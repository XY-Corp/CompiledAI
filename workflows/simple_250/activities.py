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
    
    # Extract place names for time difference query
    # Common patterns: "between X and Y", "from X to Y", "X and Y"
    params = {}
    
    # Pattern 1: "between X and Y"
    match = re.search(r'between\s+([A-Za-z\s]+?)\s+and\s+([A-Za-z\s]+?)(?:\?|$|\.)', query, re.IGNORECASE)
    if match:
        place1 = match.group(1).strip()
        place2 = match.group(2).strip()
    else:
        # Pattern 2: "from X to Y"
        match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\?|$|\.)', query, re.IGNORECASE)
        if match:
            place1 = match.group(1).strip()
            place2 = match.group(2).strip()
        else:
            # Pattern 3: "X and Y" (general)
            match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+and\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', query)
            if match:
                place1 = match.group(1).strip()
                place2 = match.group(2).strip()
            else:
                # Fallback: extract capitalized words as potential place names
                places = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', query)
                # Filter out common words
                common_words = {'What', 'The', 'Get', 'Find', 'Show', 'Tell', 'Time'}
                places = [p for p in places if p not in common_words]
                
                if len(places) >= 2:
                    place1 = places[0]
                    place2 = places[1]
                elif len(places) == 1:
                    place1 = places[0]
                    place2 = "<UNKNOWN>"
                else:
                    place1 = "<UNKNOWN>"
                    place2 = "<UNKNOWN>"
    
    # Map to parameter names from schema
    param_names = list(params_schema.keys())
    if len(param_names) >= 2:
        params[param_names[0]] = place1
        params[param_names[1]] = place2
    elif len(param_names) == 1:
        params[param_names[0]] = place1
    
    return {func_name: params}
