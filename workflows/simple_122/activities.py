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
            # Look for array patterns like [[10, 20], [30, 40]] or [ [10, 20], [30, 40] ]
            # Match 2D arrays (contingency tables)
            array_2d_match = re.search(r'\[\s*\[\s*[\d,\s]+\]\s*,\s*\[\s*[\d,\s]+\]\s*\]', query)
            if array_2d_match:
                try:
                    array_str = array_2d_match.group(0)
                    params[param_name] = json.loads(array_str)
                except json.JSONDecodeError:
                    pass
            else:
                # Try to find any array pattern
                array_match = re.search(r'\[[\d,\s\[\]]+\]', query)
                if array_match:
                    try:
                        params[param_name] = json.loads(array_match.group(0))
                    except json.JSONDecodeError:
                        pass
        
        elif param_type in ["float", "number"]:
            # Look for float values, often after keywords like "alpha", "significance", "level"
            # Check for explicit parameter mentions
            float_pattern = re.search(rf'{param_name}\s*[=:]\s*([\d.]+)', query, re.IGNORECASE)
            if float_pattern:
                params[param_name] = float(float_pattern.group(1))
            else:
                # Look for significance level patterns
                sig_pattern = re.search(r'(?:significance|alpha|level)\s*(?:of|=|:)?\s*(0?\.\d+)', query, re.IGNORECASE)
                if sig_pattern:
                    params[param_name] = float(sig_pattern.group(1))
                # Don't add default - let the function use its own default
        
        elif param_type == "integer":
            # Extract integers
            int_pattern = re.search(rf'{param_name}\s*[=:]\s*(\d+)', query, re.IGNORECASE)
            if int_pattern:
                params[param_name] = int(int_pattern.group(1))
            elif param_name in required_params:
                # Try to find any standalone integer
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Extract string values - look for quoted strings or after parameter name
            string_pattern = re.search(rf'{param_name}\s*[=:]\s*["\']?([^"\']+)["\']?', query, re.IGNORECASE)
            if string_pattern:
                params[param_name] = string_pattern.group(1).strip()
    
    return {func_name: params}
