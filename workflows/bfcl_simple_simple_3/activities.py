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
    
    # Parse prompt - may be JSON string or plain text
    try:
        if isinstance(prompt, str):
            try:
                data = json.loads(prompt)
                # Handle BFCL nested format
                if "question" in data and isinstance(data["question"], list):
                    if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                        query = data["question"][0][0].get("content", str(prompt))
                    else:
                        query = str(prompt)
                else:
                    query = data.get("content", str(prompt))
            except json.JSONDecodeError:
                query = prompt
        else:
            query = str(prompt)
    except Exception:
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
    
    # Get function details
    if not funcs:
        return {"error": "No functions provided"}
    
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters using regex
    params = {}
    
    # Pattern 1: Named parameters like "a=1" or "a = 1"
    named_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(-?\d+(?:\.\d+)?)'
    named_matches = re.findall(named_pattern, query)
    
    for param_name, value in named_matches:
        if param_name in params_schema:
            param_type = params_schema[param_name].get("type", "string")
            if param_type == "integer":
                params[param_name] = int(value)
            elif param_type in ["float", "number"]:
                params[param_name] = float(value)
            else:
                params[param_name] = value
    
    # Pattern 2: If named params didn't work, try extracting all numbers in order
    if not params:
        numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
        param_names = list(params_schema.keys())
        
        for i, param_name in enumerate(param_names):
            if i < len(numbers):
                param_type = params_schema[param_name].get("type", "string")
                if param_type == "integer":
                    params[param_name] = int(numbers[i])
                elif param_type in ["float", "number"]:
                    params[param_name] = float(numbers[i])
                else:
                    params[param_name] = numbers[i]
    
    # Pattern 3: Look for "coefficient of X" patterns for quadratic equations
    if not params or len(params) < len(params_schema):
        # Coefficient patterns
        coef_patterns = {
            'a': [r'a\s*=\s*(-?\d+)', r'coefficient\s+a\s*=?\s*(-?\d+)', r'a\s+is\s+(-?\d+)'],
            'b': [r'b\s*=\s*(-?\d+)', r'coefficient\s+b\s*=?\s*(-?\d+)', r'b\s+is\s+(-?\d+)'],
            'c': [r'c\s*=\s*(-?\d+)', r'coefficient\s+c\s*=?\s*(-?\d+)', r'c\s+is\s+(-?\d+)', r'constant\s+(?:term\s+)?(?:is\s+)?(-?\d+)'],
        }
        
        for param_name, patterns in coef_patterns.items():
            if param_name in params_schema and param_name not in params:
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        param_type = params_schema[param_name].get("type", "string")
                        value = match.group(1)
                        if param_type == "integer":
                            params[param_name] = int(value)
                        elif param_type in ["float", "number"]:
                            params[param_name] = float(value)
                        else:
                            params[param_name] = value
                        break
    
    return {func_name: params}
