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
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_list = data.get("question", [])
            if question_list and isinstance(question_list[0], list) and question_list[0]:
                query = question_list[0][0].get("content", str(prompt))
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
    
    # Extract numbers from query using regex
    # Pattern matches integers and floats
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Build parameters dict by matching extracted numbers to schema
    params = {}
    param_names = list(params_schema.keys())
    
    # Assign numbers to parameters in order
    for i, param_name in enumerate(param_names):
        param_info = params_schema.get(param_name, {})
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"] and i < len(numbers):
            if param_type == "integer":
                params[param_name] = int(numbers[i])
            else:
                params[param_name] = float(numbers[i])
    
    return {func_name: params}
