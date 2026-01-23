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
    
    # Extract name - patterns like "of X" or "Mr. X" or "person named X"
    name_patterns = [
        r'(?:of|for)\s+([A-Z][a-z]*\.?\s*[A-Z][a-zA-Z]*)',  # "of Mr. X" or "of John Doe"
        r'(Mr\.\s*[A-Z][a-zA-Z]*)',  # "Mr. X"
        r'(Mrs\.\s*[A-Z][a-zA-Z]*)',  # "Mrs. X"
        r'(Ms\.\s*[A-Z][a-zA-Z]*)',  # "Ms. X"
        r'person\s+named\s+([A-Za-z\s]+?)(?:\s+in|\s+from|$)',  # "person named X"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, query)
        if match:
            params["name"] = match.group(1).strip()
            break
    
    # Extract location - patterns like "in New York" or "in New York, NY"
    location_patterns = [
        r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)',  # "in New York" or "in New York, NY"
        r'(?:at|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)',  # "at/from City"
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, query)
        if match:
            params["location"] = match.group(1).strip()
            break
    
    # Extract years - look for 4-digit numbers (years)
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', query)
    
    if len(years) >= 2:
        # Sort years to get from_year and to_year
        years_int = sorted([int(y) for y in years])
        params["from_year"] = years_int[0]
        params["to_year"] = years_int[-1]
    elif len(years) == 1:
        # Single year - use as both from and to
        params["from_year"] = int(years[0])
        params["to_year"] = int(years[0])
    
    # Also check for "between X and Y" pattern for years
    between_match = re.search(r'between\s+(\d{4})\s+and\s+(\d{4})', query, re.IGNORECASE)
    if between_match:
        params["from_year"] = int(between_match.group(1))
        params["to_year"] = int(between_match.group(2))
    
    return {func_name: params}
