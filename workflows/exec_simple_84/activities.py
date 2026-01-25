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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            # Look for array patterns like [[1,1], [2,2], ...] or coordinates
            # Pattern for nested arrays (list of points)
            array_pattern = r'\[\s*\[[\d\s,\[\].-]+\]\s*\]'
            match = re.search(array_pattern, query)
            
            if match:
                try:
                    # Parse the matched array
                    array_str = match.group(0)
                    parsed_array = json.loads(array_str)
                    params[param_name] = parsed_array
                except json.JSONDecodeError:
                    # Try to extract individual coordinate pairs
                    coord_pattern = r'\[(\d+)\s*,\s*(\d+)\]'
                    coords = re.findall(coord_pattern, query)
                    if coords:
                        params[param_name] = [[int(x), int(y)] for x, y in coords]
            else:
                # Fallback: extract individual coordinate pairs
                coord_pattern = r'\[(\d+)\s*,\s*(\d+)\]'
                coords = re.findall(coord_pattern, query)
                if coords:
                    params[param_name] = [[int(x), int(y)] for x, y in coords]
        
        elif param_type in ["integer", "number"]:
            # Extract numbers
            numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Extract string values - look for quoted strings or after keywords
            quoted = re.search(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted.group(1)
            else:
                # Try to extract after common keywords
                keyword_match = re.search(r'(?:for|in|of|with|named?)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|\.)|$)', query, re.IGNORECASE)
                if keyword_match:
                    params[param_name] = keyword_match.group(1).strip()
    
    return {func_name: params}
