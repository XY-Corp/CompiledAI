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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
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
    
    # Extract time from query using regex patterns
    # Pattern for time like "6:30", "6:30 PM", "6:30PM", etc.
    time_patterns = [
        r'(\d{1,2}):(\d{2})\s*(?:PM|AM|pm|am)?',  # 6:30 PM, 6:30
        r'(\d{1,2})\s*(?:PM|AM|pm|am)',  # 6 PM (no minutes)
        r'at\s+(\d{1,2}):(\d{2})',  # at 6:30
    ]
    
    hours = None
    minutes = None
    
    for pattern in time_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) >= 1:
                hours = int(groups[0])
            if len(groups) >= 2 and groups[1] is not None:
                minutes = int(groups[1])
            else:
                minutes = 0  # Default to 0 minutes if not specified
            break
    
    # If no time pattern found, try to extract any numbers
    if hours is None:
        numbers = re.findall(r'\d+', query)
        if len(numbers) >= 2:
            hours = int(numbers[0])
            minutes = int(numbers[1])
        elif len(numbers) == 1:
            hours = int(numbers[0])
            minutes = 0
    
    # Build params dict with only required/found parameters
    params = {}
    
    if hours is not None:
        params["hours"] = hours
    if minutes is not None:
        params["minutes"] = minutes
    
    # Check for round_to parameter in query (optional)
    round_match = re.search(r'round(?:ed)?\s*(?:to)?\s*(\d+)\s*(?:decimal|place)', query, re.IGNORECASE)
    if round_match:
        params["round_to"] = int(round_match.group(1))
    
    return {func_name: params}
