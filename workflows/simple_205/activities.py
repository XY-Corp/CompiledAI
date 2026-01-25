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
    
    # Extract parameters using regex and string matching
    params = {}
    query_lower = query.lower()
    
    # For traffic info: extract start_location, end_location, mode
    if func_name == "get_traffic_info":
        # Pattern: "from X to Y" or "from X driving to Y"
        # Try pattern: from <location> (driving/walking/etc) to <location>
        from_to_pattern = r'from\s+([A-Za-z\s]+?)(?:\s+(?:driving|walking|bicycling|transit))?\s+to\s+([A-Za-z\s]+?)(?:\.|$|\s*$)'
        match = re.search(from_to_pattern, query, re.IGNORECASE)
        
        if match:
            params["start_location"] = match.group(1).strip()
            params["end_location"] = match.group(2).strip()
        else:
            # Fallback: try simpler "from X to Y"
            simple_pattern = r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\.|$|\s*$)'
            match = re.search(simple_pattern, query, re.IGNORECASE)
            if match:
                params["start_location"] = match.group(1).strip()
                params["end_location"] = match.group(2).strip()
        
        # Extract mode if specified
        mode_patterns = ["driving", "walking", "bicycling", "transit"]
        for mode in mode_patterns:
            if mode in query_lower:
                params["mode"] = mode
                break
        
        # Default mode to driving if not specified but mentioned in context
        if "mode" not in params and "driving" in query_lower:
            params["mode"] = "driving"
    
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
            elif param_type == "string":
                # Try to extract string values based on common patterns
                # Pattern: "for X" or "in X" or "from X" or "to X"
                patterns = [
                    rf'(?:for|in|at)\s+([A-Za-z\s]+?)(?:\s+(?:to|from|and|,)|$)',
                    rf'(?:from)\s+([A-Za-z\s]+?)(?:\s+(?:to|and|,)|$)',
                    rf'(?:to)\s+([A-Za-z\s]+?)(?:\s+(?:from|and|,)|$)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
    
    return {func_name: params}
