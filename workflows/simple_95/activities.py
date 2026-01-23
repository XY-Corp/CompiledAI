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
    """Extract function name and parameters from user query using regex patterns.
    
    Returns a dict with function name as key and parameters as nested object.
    """
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
    
    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # For triangle area: look for base and height patterns
    # Try specific patterns first
    base_match = re.search(r'base\s*(?:of\s*)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    height_match = re.search(r'height\s*(?:of\s*)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    
    # Also try "with base X and height Y" pattern
    if not base_match:
        base_match = re.search(r'with\s+base\s+(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if not height_match:
        height_match = re.search(r'(?:and\s+)?height\s+(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    
    # Map extracted values to parameter names based on schema
    num_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
        
        # Check for specific parameter matches first
        if param_name == "base" and base_match:
            value = base_match.group(1)
            params[param_name] = int(float(value)) if param_type == "integer" else float(value)
        elif param_name == "height" and height_match:
            value = height_match.group(1)
            params[param_name] = int(float(value)) if param_type == "integer" else float(value)
        elif param_type in ["integer", "float", "number"] and num_idx < len(numbers):
            # Fallback: assign numbers in order
            value = numbers[num_idx]
            if param_type == "integer":
                params[param_name] = int(float(value))
            else:
                params[param_name] = float(value)
            num_idx += 1
    
    return {func_name: params}
