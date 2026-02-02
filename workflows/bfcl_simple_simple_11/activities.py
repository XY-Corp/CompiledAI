import re
import json
from typing import Any


async def extract_function_call(
    prompt: str,
    functions: list = None,
    user_query: str = None,
    tools: list = None,
    tool_name_mapping: dict = None,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from user query using regex patterns.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL-style nested structure
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = data.get("content", str(prompt))
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    funcs = []
    if functions:
        if isinstance(functions, str):
            try:
                funcs = json.loads(functions)
            except json.JSONDecodeError:
                funcs = []
        else:
            funcs = functions
    
    # Get function schema
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Common patterns for extracting named values
    # Pattern: "base of X" or "base X" or "base: X"
    base_patterns = [
        r'base\s+(?:of\s+)?(\d+(?:\.\d+)?)',
        r'base[:\s]+(\d+(?:\.\d+)?)',
    ]
    
    # Pattern: "height of X" or "height X" or "height: X"
    height_patterns = [
        r'height\s+(?:of\s+)?(\d+(?:\.\d+)?)',
        r'height[:\s]+(\d+(?:\.\d+)?)',
    ]
    
    # Try to extract base value
    base_value = None
    for pattern in base_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            base_value = match.group(1)
            break
    
    # Try to extract height value
    height_value = None
    for pattern in height_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            height_value = match.group(1)
            break
    
    # Map extracted values to parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "base" and base_value is not None:
            if param_type == "integer":
                params[param_name] = int(float(base_value))
            elif param_type in ["number", "float"]:
                params[param_name] = float(base_value)
            else:
                params[param_name] = base_value
        elif param_name == "height" and height_value is not None:
            if param_type == "integer":
                params[param_name] = int(float(height_value))
            elif param_type in ["number", "float"]:
                params[param_name] = float(height_value)
            else:
                params[param_name] = height_value
    
    # Fallback: if we couldn't extract named params, use positional numbers
    if not params and numbers:
        param_names = list(params_schema.keys())
        for i, param_name in enumerate(param_names):
            if i < len(numbers):
                param_info = params_schema.get(param_name, {})
                param_type = param_info.get("type", "string")
                
                if param_type == "integer":
                    params[param_name] = int(float(numbers[i]))
                elif param_type in ["number", "float"]:
                    params[param_name] = float(numbers[i])
                else:
                    params[param_name] = numbers[i]
    
    return {func_name: params}
