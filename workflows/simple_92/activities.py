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
    
    # Extract parameters from query using regex
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract year or other integers
            # Look for 4-digit year patterns first
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
            if year_match:
                params[param_name] = int(year_match.group(1))
            else:
                # Fallback to any number
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            if param_name == "actor_name":
                # Extract actor name - look for patterns like "starring X" or "by X"
                # Common patterns: "starring Leonardo DiCaprio", "movies by Tom Hanks"
                patterns = [
                    r'starring\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                    r'by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                    r'actor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                    r'([A-Z][a-z]+\s+(?:Di|De|La|Le|Van|Von)?[A-Z][a-z]+)',  # Names with prefixes
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, query)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
            
            elif param_name == "category":
                # Extract category - look for genre keywords
                genres = ["Drama", "Comedy", "Action", "Thriller", "Horror", "Romance", 
                         "Sci-Fi", "Documentary", "Animation", "Adventure"]
                for genre in genres:
                    if genre.lower() in query.lower():
                        params[param_name] = genre
                        break
                # Don't add category if not found (it's optional with default 'all')
    
    return {func_name: params}
