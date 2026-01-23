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
    
    # Extract parameters from query
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "string":
            # Extract location/city - look for patterns like "in [City], [State]" or "in [City]"
            if param_name == "location":
                # Pattern: "in City, State" or "in City State" or "for City"
                location_patterns = [
                    r'(?:in|for|at)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*,\s*[A-Za-z]+(?:\s+[A-Za-z]+)*)',  # City, State
                    r'(?:in|for|at)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',  # Just city/location
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
        
        elif param_type == "integer":
            # Extract numbers with context
            if param_name == "days":
                # Look for patterns like "7 days", "next 7 days", "upcoming 7 days"
                days_patterns = [
                    r'(?:next|upcoming|following|for)\s+(\d+)\s+days?',
                    r'(\d+)\s+days?\s+(?:forecast|ahead|from)',
                    r'(\d+)\s+days?',
                ]
                for pattern in days_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = int(match.group(1))
                        break
            elif param_name == "min_humidity":
                # Look for minimum humidity patterns
                humidity_patterns = [
                    r'(?:min(?:imum)?|at least)\s+(\d+)\s*%?\s*humidity',
                    r'humidity\s+(?:above|over|greater than|at least)\s+(\d+)',
                ]
                for pattern in humidity_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = int(match.group(1))
                        break
            else:
                # Generic number extraction for other integer params
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = int(numbers[0])
    
    return {func_name: params}
