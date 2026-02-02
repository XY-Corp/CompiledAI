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
    """Extract function name and parameters from user prompt using regex/parsing.
    
    Returns format: {"function_name": {"param1": val1, ...}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            try:
                data = json.loads(prompt)
                # Handle BFCL-style nested format
                if "question" in data and isinstance(data["question"], list):
                    if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                        query = data["question"][0][0].get("content", prompt)
                    else:
                        query = str(data["question"])
                else:
                    query = str(data)
            except json.JSONDecodeError:
                query = prompt
        else:
            query = str(prompt)
    except Exception:
        query = str(prompt)

    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except Exception:
        funcs = []

    # Get first function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "unknown")
    
    # Get parameters schema - handle both 'parameters' and 'params' keys
    params_schema = func.get("parameters", func.get("params", {}))
    if isinstance(params_schema, dict):
        props = params_schema.get("properties", params_schema)
    else:
        props = {}

    # Extract all numbers from query
    numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
    
    # Extract string values (words after common prepositions)
    string_match = re.search(r'(?:for|in|of|with|to|from)\s+([A-Za-z][A-Za-z\s]*?)(?:\s+(?:and|with|,|$))', query, re.IGNORECASE)
    string_value = string_match.group(1).strip() if string_match else None

    # Build params dict based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in props.items():
        # Handle both string format ("string") and dict format ({"type": "string"})
        if isinstance(param_info, str):
            param_type = param_info
        else:
            param_type = param_info.get("type", "string")
        
        # Assign values based on type
        if param_type in ["integer", "int"] and num_idx < len(numbers):
            params[param_name] = int(float(numbers[num_idx]))
            num_idx += 1
        elif param_type in ["number", "float"] and num_idx < len(numbers):
            params[param_name] = float(numbers[num_idx])
            num_idx += 1
        elif param_type == "string" and string_value:
            params[param_name] = string_value
            string_value = None  # Use only once

    # If no schema but we have numbers, try common patterns
    if not props and numbers:
        # Check for arithmetic operations
        if '+' in query or 'add' in query.lower() or 'plus' in query.lower() or 'sum' in query.lower():
            if len(numbers) >= 2:
                params = {"a": int(float(numbers[0])), "b": int(float(numbers[1]))}
                if not func_name or func_name == "unknown":
                    func_name = "add"
        elif '-' in query or 'subtract' in query.lower() or 'minus' in query.lower():
            if len(numbers) >= 2:
                params = {"a": int(float(numbers[0])), "b": int(float(numbers[1]))}
                if not func_name or func_name == "unknown":
                    func_name = "subtract"
        elif '*' in query or 'multiply' in query.lower() or 'times' in query.lower():
            if len(numbers) >= 2:
                params = {"a": int(float(numbers[0])), "b": int(float(numbers[1]))}
                if not func_name or func_name == "unknown":
                    func_name = "multiply"
        elif '/' in query or 'divide' in query.lower():
            if len(numbers) >= 2:
                params = {"a": int(float(numbers[0])), "b": int(float(numbers[1]))}
                if not func_name or func_name == "unknown":
                    func_name = "divide"
        elif 'factorial' in query.lower():
            params = {"n": int(float(numbers[0]))}
            if not func_name or func_name == "unknown":
                func_name = "factorial"
        elif 'gcd' in query.lower() or 'greatest common' in query.lower():
            if len(numbers) >= 2:
                params = {"a": int(float(numbers[0])), "b": int(float(numbers[1]))}
                if not func_name or func_name == "unknown":
                    func_name = "gcd"
        elif len(numbers) == 1:
            params = {"n": int(float(numbers[0]))}
        elif len(numbers) >= 2:
            params = {"a": int(float(numbers[0])), "b": int(float(numbers[1]))}

    return {func_name: params}
