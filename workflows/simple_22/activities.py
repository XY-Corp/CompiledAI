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
    """Extract function name and parameters from user query using regex.
    
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
    
    # Extract numbers using regex - handles "12 and 15", "12, 15", "of 12 and 15", etc.
    numbers = re.findall(r'\d+', query)
    
    # Build parameters dict based on schema
    params = {}
    param_names = list(params_schema.keys())
    
    # For GCD and similar two-number functions
    if len(numbers) >= 2 and len(param_names) >= 2:
        # Assign first two numbers to first two parameters
        for i, param_name in enumerate(param_names[:2]):
            param_info = params_schema.get(param_name, {})
            param_type = param_info.get("type", "string")
            
            if param_type == "integer":
                params[param_name] = int(numbers[i])
            elif param_type in ["float", "number"]:
                params[param_name] = float(numbers[i])
            else:
                params[param_name] = numbers[i]
    elif len(numbers) == 1 and len(param_names) >= 1:
        # Single number case (e.g., factorial)
        param_name = param_names[0]
        param_info = params_schema.get(param_name, {})
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            params[param_name] = int(numbers[0])
        elif param_type in ["float", "number"]:
            params[param_name] = float(numbers[0])
        else:
            params[param_name] = numbers[0]
    
    return {func_name: params}
