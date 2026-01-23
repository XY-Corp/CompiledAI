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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract integers - look for patterns like "100 trees", "depth of 5"
            if param_name == "n_estimators":
                # Look for number before "trees" or "estimators"
                match = re.search(r'(\d+)\s*(?:trees|estimators)', query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
            elif param_name == "max_depth":
                # Look for "depth of X" or "depth X"
                match = re.search(r'depth\s*(?:of\s*)?(\d+)', query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
            else:
                # Generic integer extraction
                numbers = re.findall(r'\d+', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "any" or param_type == "string":
            if param_name == "data":
                # Look for data reference patterns like "data my_data", "on my_data", "provided data X"
                patterns = [
                    r'(?:provided\s+)?data\s+(\w+)',
                    r'on\s+(?:the\s+)?(?:provided\s+)?(?:data\s+)?(\w+\.?\w*)',
                    r'dataset\s+(\w+)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        data_val = match.group(1)
                        # Skip if it's just "data" without a name
                        if data_val.lower() not in ["data", "the"]:
                            params[param_name] = data_val
                            break
            else:
                # Generic string extraction - look for quoted strings or identifiers
                quoted = re.search(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted.group(1)
    
    return {func_name: params}
