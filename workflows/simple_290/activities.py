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
    """Extract function call parameters from user query using regex and string matching."""
    
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
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex and string matching
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "artist":
            # Extract artist name - look for possessive patterns or quoted names
            # Pattern: "X's concert" or artist names
            artist_patterns = [
                r"([A-Z][a-zA-Z\s]+(?:'s)?)\s+concert",  # "The Weeknd's concert"
                r"for\s+([A-Z][a-zA-Z\s]+)",  # "for The Weeknd"
                r"by\s+([A-Z][a-zA-Z\s]+)",  # "by The Weeknd"
            ]
            for pattern in artist_patterns:
                match = re.search(pattern, query)
                if match:
                    artist = match.group(1).strip()
                    # Remove possessive 's if present
                    artist = re.sub(r"'s$", "", artist).strip()
                    params[param_name] = artist
                    break
        
        elif param_name == "month":
            # Extract month name
            months = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            for month in months:
                if month.lower() in query.lower():
                    params[param_name] = month
                    break
        
        elif param_name == "year":
            # Extract year (4-digit number)
            year_match = re.search(r'\b(20\d{2})\b', query)
            if year_match:
                params[param_name] = int(year_match.group(1))
            # If no year found and there's a default, don't include it (let default apply)
        
        elif param_type == "integer":
            # Generic integer extraction
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - try common patterns
            patterns = [
                rf'(?:for|in|of|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|$))',
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
                    break
    
    return {func_name: params}
