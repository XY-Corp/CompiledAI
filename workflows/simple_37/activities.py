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
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
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
    
    # Extract parameters using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # For route.estimate_time: extract start_location, end_location, stops
    if func_name == "route.estimate_time":
        # Pattern: "from X to Y" for start and end locations
        from_to_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\s+with|\s*\.|\s*$)', query, re.IGNORECASE)
        
        if from_to_match:
            params["start_location"] = from_to_match.group(1).strip()
            params["end_location"] = from_to_match.group(2).strip()
        
        # Extract stops: "with stops at X and Y" or "with stops at X, Y"
        stops_match = re.search(r'(?:with\s+)?stops?\s+at\s+(.+?)(?:\.|$)', query, re.IGNORECASE)
        if stops_match:
            stops_text = stops_match.group(1).strip()
            # Split by "and" or ","
            # Handle "X and Y" or "X, Y" or "X, Y and Z"
            stops_text = re.sub(r'\s+and\s+', ', ', stops_text, flags=re.IGNORECASE)
            stops = [s.strip() for s in stops_text.split(',') if s.strip()]
            if stops:
                params["stops"] = stops
    else:
        # Generic extraction for other functions
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type in ["integer", "number", "float"]:
                # Extract numbers
                numbers = re.findall(r'\d+(?:\.\d+)?', query)
                if numbers:
                    if param_type == "integer":
                        params[param_name] = int(numbers[0])
                    else:
                        params[param_name] = float(numbers[0])
            elif param_type == "array":
                # Try to extract list items
                list_match = re.search(r'(?:with|including|:)\s*(.+?)(?:\.|$)', query, re.IGNORECASE)
                if list_match:
                    items_text = list_match.group(1)
                    items_text = re.sub(r'\s+and\s+', ', ', items_text, flags=re.IGNORECASE)
                    items = [s.strip() for s in items_text.split(',') if s.strip()]
                    params[param_name] = items
            elif param_type == "string":
                # Try common patterns for string extraction
                patterns = [
                    rf'{param_name}\s*[=:]\s*["\']?([^"\']+)["\']?',
                    rf'(?:for|in|from|to|at)\s+([A-Za-z\s]+?)(?:\s+(?:to|from|with|and)|$)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
    
    return {func_name: params}
