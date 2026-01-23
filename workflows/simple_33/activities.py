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
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on the query
    params = {}
    query_lower = query.lower()
    
    # For get_directions: extract start_location, end_location, route_type
    if func_name == "get_directions":
        # Pattern: "from X to Y"
        from_to_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\s+using|\s*\.|$)', query, re.IGNORECASE)
        if from_to_match:
            params["start_location"] = from_to_match.group(1).strip()
            params["end_location"] = from_to_match.group(2).strip()
        
        # Extract route_type if mentioned
        if "fastest" in query_lower:
            params["route_type"] = "fastest"
        elif "scenic" in query_lower:
            params["route_type"] = "scenic"
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
                    # Remove used number for next param
                    query = query.replace(numbers[0], "", 1)
            elif param_type == "string":
                # Try to extract string values based on common patterns
                # Pattern: "param_name X" or "for X" or "in X"
                patterns = [
                    rf'{param_name}\s+["\']?([^"\']+)["\']?',
                    r'(?:for|in|from|to)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|using|,)|$)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).strip()
                        break
    
    return {func_name: params}
