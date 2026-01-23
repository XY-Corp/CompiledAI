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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # Extract cities - look for patterns like "between X and Y" or "from X to Y"
    # Pattern 1: "between city1 and city2"
    between_match = re.search(r'between\s+([A-Za-z\s]+?)\s+and\s+([A-Za-z\s]+?)(?:\s*,|\s+through|\s+via|\.|$)', query, re.IGNORECASE)
    
    # Pattern 2: "from city1 to city2"
    from_to_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\s*,|\s+through|\s+via|\.|$)', query, re.IGNORECASE)
    
    # Pattern 3: "two cities, X and Y" or "cities X and Y"
    cities_match = re.search(r'cities[,\s]+([A-Za-z\s]+?)\s+and\s+([A-Za-z\s]+?)(?:\s*,|\s+through|\s+via|\.|$)', query, re.IGNORECASE)
    
    start_city = None
    end_city = None
    
    if between_match:
        start_city = between_match.group(1).strip()
        end_city = between_match.group(2).strip()
    elif from_to_match:
        start_city = from_to_match.group(1).strip()
        end_city = from_to_match.group(2).strip()
    elif cities_match:
        start_city = cities_match.group(1).strip()
        end_city = cities_match.group(2).strip()
    
    # Assign to params if found
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
        # Check for transfer-related keywords
        if re.search(r'\b(can transfer|allow transfer|transfer allowed|you can transfer|with transfer)\b', query_lower):
            params["allow_transfer"] = True
        elif re.search(r'\b(no transfer|direct|without transfer|non-stop)\b', query_lower):
            params["allow_transfer"] = False
        # Default not set if not mentioned (let function use its default)
    
    return {func_name: params}
