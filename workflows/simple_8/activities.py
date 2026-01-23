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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex to extract values - NO LLM calls needed for explicit values in text.
    """
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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameter values using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        required = param_name in func.get("parameters", {}).get("required", [])
        
        if param_type in ["integer", "number", "float"]:
            # Assign next available number to this parameter
            if num_idx < len(numbers):
                if param_type == "integer":
                    params[param_name] = int(numbers[num_idx])
                else:
                    params[param_name] = float(numbers[num_idx])
                num_idx += 1
        elif param_type == "string":
            # For string params like "units", check if explicitly mentioned
            # Common patterns: "in meters", "in feet", "using meters"
            units_match = re.search(r'(?:in|using|with)\s+([a-zA-Z]+)(?:\s|$|\.)', query, re.IGNORECASE)
            if units_match and param_name == "units":
                params[param_name] = units_match.group(1).lower()
            # Only add if required or explicitly found
            elif required:
                # Try to extract any relevant string value
                string_match = re.search(r'(?:for|of|with)\s+([a-zA-Z\s]+?)(?:\s+(?:and|with|,)|$)', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
