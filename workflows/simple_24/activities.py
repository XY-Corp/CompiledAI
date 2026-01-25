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
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
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
    
    # Extract numbers using regex - handles "GCD of 12 and 18", "12 and 18", etc.
    numbers = re.findall(r'\d+', query)
    
    # Build parameters dict matching schema
    params = {}
    param_names = list(params_schema.keys())
    
    # Assign extracted numbers to parameters in order
    for i, param_name in enumerate(param_names):
        param_info = params_schema.get(param_name, {})
        param_type = param_info.get("type", "string")
        
        if param_type == "integer" and i < len(numbers):
            params[param_name] = int(numbers[i])
        elif param_type in ["float", "number"] and i < len(numbers):
            params[param_name] = float(numbers[i])
        elif param_type == "string":
            # For string params, try to extract from patterns like "for X" or "in X"
            string_match = re.search(r'(?:for|in|of|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,)|$)', query, re.IGNORECASE)
            if string_match:
                params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
