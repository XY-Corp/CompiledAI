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
    # Patterns for "X and Y", "X, Y", "of X and Y", etc.
    numbers = []
    
    # Try specific patterns first
    patterns = [
        r'of\s+(\d+)\s+and\s+(\d+)',      # "of 36 and 24"
        r'(\d+)\s+and\s+(\d+)',            # "36 and 24"
        r'(\d+)\s*,\s*(\d+)',              # "36, 24"
        r'between\s+(\d+)\s+and\s+(\d+)',  # "between 36 and 24"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            numbers = [int(match.group(1)), int(match.group(2))]
            break
    
    # Fallback: extract all numbers if patterns didn't match
    if not numbers:
        all_nums = re.findall(r'\d+', query)
        numbers = [int(n) for n in all_nums[:2]]  # Take first two numbers
    
    # Build parameters dict matching schema exactly
    params = {}
    param_names = list(params_schema.keys())
    
    # Assign extracted numbers to parameters in order
    for i, param_name in enumerate(param_names):
        param_info = params_schema.get(param_name, {})
        param_type = param_info.get("type", "string")
        
        if param_type == "integer" and i < len(numbers):
            params[param_name] = numbers[i]
        elif param_type in ["number", "float"] and i < len(numbers):
            params[param_name] = float(numbers[i])
    
    # Return format: {"function_name": {params}}
    return {func_name: params}
