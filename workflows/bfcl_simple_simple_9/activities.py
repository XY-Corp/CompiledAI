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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
    # Step 1: Parse prompt to extract the actual user query
    query = prompt
    if isinstance(prompt, str):
        try:
            data = json.loads(prompt)
            # Handle BFCL-style nested structure
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
                elif len(data["question"]) > 0 and isinstance(data["question"][0], dict):
                    query = data["question"][0].get("content", prompt)
            elif "query" in data:
                query = data["query"]
            elif "content" in data:
                query = data["content"]
        except (json.JSONDecodeError, TypeError, KeyError):
            query = prompt
    
    # Step 2: Parse functions list
    funcs = functions
    if isinstance(functions, str):
        try:
            funcs = json.loads(functions)
        except (json.JSONDecodeError, TypeError):
            funcs = []
    
    if not funcs:
        funcs = []
    
    # Get the target function (first one in the list)
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # Get parameters schema
    params_schema = func.get("parameters", {})
    if isinstance(params_schema, dict):
        properties = params_schema.get("properties", {})
        required_params = params_schema.get("required", [])
    else:
        properties = {}
        required_params = []
    
    # Step 3: Extract parameter values using regex
    extracted_params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    number_idx = 0
    
    # Extract unit patterns
    unit_patterns = [
        r'in\s+(\w+)',
        r'(\w+)\s+units?',
        r'measured\s+in\s+(\w+)',
    ]
    
    for param_name, param_info in properties.items():
        param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
        
        if param_type in ["integer", "number", "float"]:
            # Extract numeric value
            if number_idx < len(numbers):
                value = numbers[number_idx]
                if param_type == "integer":
                    extracted_params[param_name] = int(float(value))
                else:
                    extracted_params[param_name] = float(value)
                number_idx += 1
        elif param_type == "string":
            # Check if this is a unit parameter
            if "unit" in param_name.lower():
                # Try to extract unit from query
                for pattern in unit_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        extracted_params[param_name] = match.group(1).lower()
                        break
                # If no unit found and it's not required, skip it
                if param_name not in extracted_params and param_name not in required_params:
                    continue
            else:
                # Generic string extraction - look for quoted strings or named values
                quoted_match = re.search(r'"([^"]+)"', query)
                if quoted_match:
                    extracted_params[param_name] = quoted_match.group(1)
    
    # Only include required params and optional params that were found
    final_params = {}
    for param_name in properties.keys():
        if param_name in extracted_params:
            final_params[param_name] = extracted_params[param_name]
        elif param_name in required_params:
            # Required param not found - try harder or use placeholder
            if properties[param_name].get("type") in ["integer", "number", "float"]:
                if number_idx < len(numbers):
                    val = numbers[number_idx]
                    if properties[param_name].get("type") == "integer":
                        final_params[param_name] = int(float(val))
                    else:
                        final_params[param_name] = float(val)
                    number_idx += 1
    
    return {func_name: final_params}
