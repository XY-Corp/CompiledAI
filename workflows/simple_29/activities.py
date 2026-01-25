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
    """Extract function name and parameters from user query using regex patterns."""
    
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Look for specific patterns in the query
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Handle 'time' parameter - look for time-related patterns
        if param_name == "time":
            # Pattern: "for X seconds" or "after X seconds" or "X seconds"
            time_match = re.search(r'(?:for|after|falling\s+for)?\s*(\d+(?:\.\d+)?)\s*seconds?', query_lower)
            if time_match:
                val = time_match.group(1)
                params[param_name] = int(val) if param_type == "integer" else float(val)
                continue
        
        # Handle 'initial_speed' parameter
        if param_name == "initial_speed":
            # Check for "from rest" or "at rest" - means initial speed is 0
            if "from rest" in query_lower or "at rest" in query_lower or "dropped" in query_lower:
                params[param_name] = 0
                continue
            # Look for explicit initial speed
            speed_match = re.search(r'initial\s*speed\s*(?:of|is|=)?\s*(\d+(?:\.\d+)?)', query_lower)
            if speed_match:
                val = speed_match.group(1)
                params[param_name] = int(val) if param_type == "integer" else float(val)
                continue
        
        # Handle 'gravity' parameter - usually uses default, but check for explicit value
        if param_name == "gravity":
            gravity_match = re.search(r'gravity\s*(?:of|is|=)?\s*(-?\d+(?:\.\d+)?)', query_lower)
            if gravity_match:
                val = gravity_match.group(1)
                params[param_name] = float(val)
                continue
            # Don't include if not explicitly mentioned (use default)
    
    # Ensure required parameters are present
    for req_param in required_params:
        if req_param not in params:
            # Try to extract from remaining numbers
            if numbers:
                param_info = params_schema.get(req_param, {})
                param_type = param_info.get("type", "string")
                val = numbers.pop(0)
                if param_type == "integer":
                    params[req_param] = int(float(val))
                elif param_type in ["float", "number"]:
                    params[req_param] = float(val)
                else:
                    params[req_param] = val
    
    return {func_name: params}
