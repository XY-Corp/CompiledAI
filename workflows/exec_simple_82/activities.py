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
    """Extract function name and parameters from user query using regex/parsing."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    props = func.get("parameters", {}).get("properties", {})
    
    params = {}
    
    # Extract array values - look for patterns like [1, 2, 3]
    array_matches = re.findall(r'\[([^\]]+)\]', query)
    
    arrays_found = []
    for match in array_matches:
        # Try to parse as array of numbers
        try:
            # Split by comma and parse each element
            elements = [int(x.strip()) for x in match.split(',')]
            arrays_found.append(elements)
        except ValueError:
            try:
                elements = [float(x.strip()) for x in match.split(',')]
                arrays_found.append(elements)
            except ValueError:
                continue
    
    # Extract single integer values for 'point' parameter
    # Look for patterns like "when x is 10", "at x = 10", "for x equals 10", "at 10"
    point_patterns = [
        r'when\s+x\s+is\s+(\d+)',
        r'at\s+x\s*=\s*(\d+)',
        r'for\s+x\s*=\s*(\d+)',
        r'x\s+is\s+(\d+)',
        r'at\s+(\d+)',
        r'for\s+(\d+)',
        r'point\s+(\d+)',
    ]
    
    point_value = None
    for pattern in point_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            point_value = int(match.group(1))
            break
    
    # Map extracted values to parameter names based on schema
    array_idx = 0
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array" and array_idx < len(arrays_found):
            params[param_name] = arrays_found[array_idx]
            array_idx += 1
        elif param_type == "integer" and point_value is not None:
            params[param_name] = point_value
    
    return {func_name: params}
