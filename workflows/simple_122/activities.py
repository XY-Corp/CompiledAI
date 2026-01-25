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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
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
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            # Look for array/table patterns like [[10, 20], [30, 40]]
            # Try to find nested array pattern
            array_match = re.search(r'\[\s*\[\s*[\d,\s]+\]\s*(?:,\s*\[\s*[\d,\s]+\]\s*)*\]', query)
            if array_match:
                try:
                    array_value = json.loads(array_match.group(0))
                    params[param_name] = array_value
                except json.JSONDecodeError:
                    pass
        
        elif param_type == "float":
            # Look for float values, often after keywords like "alpha", "level", "significance"
            # Check if there's a specific mention of this parameter
            param_pattern = rf'{param_name}\s*[=:]\s*([\d.]+)'
            param_match = re.search(param_pattern, query, re.IGNORECASE)
            if param_match:
                try:
                    params[param_name] = float(param_match.group(1))
                except ValueError:
                    pass
            else:
                # Look for significance level mentions
                sig_pattern = r'(?:significance|alpha|level)\s*(?:of|=|:)?\s*([\d.]+)'
                sig_match = re.search(sig_pattern, query, re.IGNORECASE)
                if sig_match:
                    try:
                        params[param_name] = float(sig_match.group(1))
                    except ValueError:
                        pass
                # Don't add default - only add if explicitly mentioned or required
        
        elif param_type == "integer":
            # Extract integers
            int_match = re.search(rf'{param_name}\s*[=:]\s*(\d+)', query, re.IGNORECASE)
            if int_match:
                params[param_name] = int(int_match.group(1))
        
        elif param_type == "string":
            # Extract string values - look for quoted strings or after parameter name
            str_pattern = rf'{param_name}\s*[=:]\s*["\']?([^"\']+)["\']?'
            str_match = re.search(str_pattern, query, re.IGNORECASE)
            if str_match:
                params[param_name] = str_match.group(1).strip()
    
    return {func_name: params}
