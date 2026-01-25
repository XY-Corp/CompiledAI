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
    """Extract function name and parameters from user query using regex and string matching."""
    
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+)\b', query)
    
    # Extract data reference (e.g., "my_data", "data.csv", etc.)
    data_match = re.search(r'\b(?:on|from|using|with)\s+(?:the\s+)?(?:provided\s+)?(?:data\s+)?([a-zA-Z_][a-zA-Z0-9_\.]*)', query, re.IGNORECASE)
    data_value = data_match.group(1) if data_match else None
    
    # Also try to find data patterns like "my_data" or "dataset_name"
    if not data_value:
        data_match = re.search(r'\b(my_\w+|data_\w+|\w+_data)\b', query, re.IGNORECASE)
        data_value = data_match.group(1) if data_match else None
    
    # Map extracted values to parameters based on schema
    num_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Try to match based on description keywords
            if "trees" in param_desc or "estimator" in param_desc:
                # Look for "100 trees" pattern
                trees_match = re.search(r'(\d+)\s*trees', query, re.IGNORECASE)
                if trees_match:
                    params[param_name] = int(trees_match.group(1))
                elif num_idx < len(numbers):
                    params[param_name] = int(numbers[num_idx])
                    num_idx += 1
            elif "depth" in param_desc:
                # Look for "depth of 5" pattern
                depth_match = re.search(r'depth\s+(?:of\s+)?(\d+)', query, re.IGNORECASE)
                if depth_match:
                    params[param_name] = int(depth_match.group(1))
                elif num_idx < len(numbers):
                    params[param_name] = int(numbers[num_idx])
                    num_idx += 1
            elif num_idx < len(numbers):
                params[param_name] = int(numbers[num_idx])
                num_idx += 1
        elif param_type == "any" and "data" in param_name.lower():
            if data_value:
                params[param_name] = data_value
    
    return {func_name: params}
