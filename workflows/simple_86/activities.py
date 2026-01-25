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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question = data["question"]
            if isinstance(question, list) and len(question) > 0:
                if isinstance(question[0], list) and len(question[0]) > 0:
                    query = question[0][0].get("content", str(prompt))
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract city names - look for patterns like "between X and Y" or "from X to Y"
    # Pattern 1: "between city1 and city2"
    between_match = re.search(r'between\s+([A-Za-z\s]+?)\s+and\s+([A-Za-z\s]+?)(?:\s*,|\s+through|\s+via|\.|$)', query, re.IGNORECASE)
    
    # Pattern 2: "from city1 to city2"
    from_to_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\s*,|\s+through|\s+via|\.|$)', query, re.IGNORECASE)
    
    start_city = None
    end_city = None
    
    if between_match:
        start_city = between_match.group(1).strip()
        end_city = between_match.group(2).strip()
    elif from_to_match:
        start_city = from_to_match.group(1).strip()
        end_city = from_to_match.group(2).strip()
    else:
        # Fallback: look for known city names or capitalized words
        # Pattern: "two cities, City1 and City2"
        cities_match = re.search(r'cities[,\s]+([A-Z][a-zA-Z\s]+?)\s+and\s+([A-Z][a-zA-Z\s]+?)(?:\s*,|\s+through|\s+via|\.|$)', query)
        if cities_match:
            start_city = cities_match.group(1).strip()
            end_city = cities_match.group(2).strip()
    
    if start_city and "start_city" in params_schema:
        params["start_city"] = start_city
    if end_city and "end_city" in params_schema:
        params["end_city"] = end_city
    
    # Extract transportation mode
    if "transportation" in params_schema:
        transport_modes = ["train", "bus", "subway", "metro", "tram", "ferry", "plane", "flight"]
        for mode in transport_modes:
            if mode in query_lower:
                params["transportation"] = mode
                break
    
    # Extract allow_transfer boolean
    if "allow_transfer" in params_schema:
        # Look for transfer-related keywords
        if "transfer" in query_lower or "can transfer" in query_lower or "allow transfer" in query_lower:
            params["allow_transfer"] = True
        elif "no transfer" in query_lower or "direct" in query_lower or "without transfer" in query_lower:
            params["allow_transfer"] = False
        # If "you can transfer" is mentioned, it's True
        if re.search(r'you\s+can\s+transfer', query_lower):
            params["allow_transfer"] = True
    
    return {func_name: params}
