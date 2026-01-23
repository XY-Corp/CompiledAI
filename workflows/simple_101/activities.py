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
    """Extract function call parameters from natural language query.
    
    Parses the prompt to extract the user query, then uses regex to extract
    parameter values based on the function schema.
    """
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
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            if num_idx < len(numbers):
                params[param_name] = int(float(numbers[num_idx]))
                num_idx += 1
        elif param_type == "number" or param_type == "float":
            if num_idx < len(numbers):
                params[param_name] = float(numbers[num_idx])
                num_idx += 1
        elif param_type == "string":
            # For string params, look for specific patterns
            # Check for unit specification (km/h, m/s, mph, etc.)
            if "unit" in param_name.lower():
                unit_match = re.search(r'\b(km/h|m/s|mph|km/s|ft/s|knots?)\b', query, re.IGNORECASE)
                if unit_match:
                    params[param_name] = unit_match.group(1).lower()
    
    return {func_name: params}
