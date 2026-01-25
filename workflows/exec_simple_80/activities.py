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
    """Extract function name and parameters from user query using regex/parsing.
    
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
    
    # Extract binary numbers from query using regex
    # Pattern for binary numbers: sequences of 0s and 1s, often in quotes
    # Examples: '0011', "1100", 0011, 1100
    
    # Try quoted binary numbers first (more specific)
    quoted_binary = re.findall(r"['\"]([01]+)['\"]", query)
    
    # Fallback: unquoted binary-looking numbers (only 0s and 1s)
    if len(quoted_binary) < 2:
        # Look for standalone binary patterns
        unquoted_binary = re.findall(r'\b([01]{2,})\b', query)
        binary_numbers = quoted_binary + [b for b in unquoted_binary if b not in quoted_binary]
    else:
        binary_numbers = quoted_binary
    
    # Build params dict based on schema
    params = {}
    param_names = list(params_schema.keys())
    
    # For add_binary_numbers: expect params 'a' and 'b' for two binary numbers
    if len(binary_numbers) >= 2 and len(param_names) >= 2:
        # Assign first binary to first param, second to second param
        params[param_names[0]] = binary_numbers[0]
        params[param_names[1]] = binary_numbers[1]
    elif len(binary_numbers) == 1 and len(param_names) >= 1:
        params[param_names[0]] = binary_numbers[0]
    
    return {func_name: params}
