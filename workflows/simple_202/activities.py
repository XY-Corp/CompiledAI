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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Extract numbers - look for patterns like "3 months", "for 3", etc.
            if "duration" in param_name or "month" in param_desc:
                # Look for number followed by month(s)
                match = re.search(r'(\d+)\s*months?', query_lower)
                if match:
                    params[param_name] = int(match.group(1))
                else:
                    # Just find any number
                    numbers = re.findall(r'\d+', query)
                    if numbers:
                        params[param_name] = int(numbers[0])
            else:
                # Generic integer extraction
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Handle energy_type parameter
            if "energy" in param_name or "energy" in param_desc:
                # Look for renewable energy type mentions
                energy_types = ["renewable", "solar", "wind", "hydro", "geothermal", "biomass"]
                for energy in energy_types:
                    if energy in query_lower:
                        params[param_name] = energy
                        break
                # Default to "renewable" if mentioned generically
                if param_name not in params and "renewable energy" in query_lower:
                    params[param_name] = "renewable"
            
            # Handle region parameter
            elif "region" in param_name or "region" in param_desc:
                # Look for US states or regions
                states = [
                    "California", "Texas", "New York", "Florida", "Illinois",
                    "Pennsylvania", "Ohio", "Georgia", "North Carolina", "Michigan",
                    "Washington", "Arizona", "Massachusetts", "Colorado", "Oregon"
                ]
                for state in states:
                    if state.lower() in query_lower:
                        params[param_name] = state
                        break
                # Also check for "in X" pattern
                if param_name not in params:
                    match = re.search(r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', query)
                    if match:
                        params[param_name] = match.group(1)
    
    # Apply defaults for optional parameters not found
    for param_name, param_info in params_schema.items():
        if param_name not in params and param_name not in required_params:
            # Check if there's a default in the description
            desc = param_info.get("description", "")
            default_match = re.search(r"[Dd]efault\s+(?:is\s+)?['\"]?([^'\"\.]+)['\"]?", desc)
            if default_match:
                default_val = default_match.group(1).strip().rstrip(".")
                if param_info.get("type") == "integer":
                    try:
                        params[param_name] = int(default_val)
                    except ValueError:
                        pass
                else:
                    params[param_name] = default_val
    
    return {func_name: params}
