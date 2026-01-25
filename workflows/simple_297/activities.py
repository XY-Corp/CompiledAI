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
    """Extract function call from prompt and return as {func_name: {params}}."""
    
    # Parse prompt (may be JSON string)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from nested structure
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    props = func.get("parameters", {}).get("properties", {})
    
    # The query looks like a function call: music.theory.chordProgression(progression=['I', 'V', 'vi', 'IV'])
    # Extract parameters from the function call syntax
    params = {}
    
    # Try to extract function call pattern: funcName(param1=val1, param2=val2, ...)
    func_call_match = re.search(r'\w+(?:\.\w+)*\s*\((.+)\)\s*$', query, re.DOTALL)
    
    if func_call_match:
        args_str = func_call_match.group(1)
        
        # Extract each parameter
        for param_name, param_info in props.items():
            param_type = param_info.get("type", "string")
            
            # Pattern to match param_name=value
            if param_type == "array":
                # Match array: param_name=[...]
                array_pattern = rf'{param_name}\s*=\s*(\[[^\]]*\])'
                array_match = re.search(array_pattern, args_str)
                if array_match:
                    try:
                        # Parse the array - handle single quotes by replacing with double quotes
                        array_str = array_match.group(1).replace("'", '"')
                        params[param_name] = json.loads(array_str)
                    except json.JSONDecodeError:
                        # Fallback: extract items manually
                        items_match = re.findall(r"'([^']*)'|\"([^\"]*)\"", array_match.group(1))
                        params[param_name] = [m[0] or m[1] for m in items_match]
            
            elif param_type == "boolean":
                # Match boolean: param_name=True/False/true/false
                bool_pattern = rf'{param_name}\s*=\s*(True|False|true|false)'
                bool_match = re.search(bool_pattern, args_str)
                if bool_match:
                    params[param_name] = bool_match.group(1).lower() == "true"
            
            elif param_type in ["integer", "number"]:
                # Match number: param_name=123 or param_name=123.45
                num_pattern = rf'{param_name}\s*=\s*(-?\d+(?:\.\d+)?)'
                num_match = re.search(num_pattern, args_str)
                if num_match:
                    val = num_match.group(1)
                    params[param_name] = int(val) if param_type == "integer" else float(val)
            
            else:
                # Match string: param_name='value' or param_name="value"
                str_pattern = rf"{param_name}\s*=\s*['\"]([^'\"]*)['\"]"
                str_match = re.search(str_pattern, args_str)
                if str_match:
                    params[param_name] = str_match.group(1)
    
    return {func_name: params}
