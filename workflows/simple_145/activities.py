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
    """Extract function call parameters from user query using regex patterns."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Extract all numbers from the query
    # Pattern matches integers and floats, including those with $ or % symbols
    numbers = re.findall(r'\$?([\d,]+(?:\.\d+)?)\s*%?', query)
    # Clean numbers (remove commas)
    cleaned_numbers = [n.replace(',', '') for n in numbers if n]
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            if num_idx < len(cleaned_numbers):
                try:
                    params[param_name] = int(float(cleaned_numbers[num_idx]))
                    num_idx += 1
                except ValueError:
                    pass
        elif param_type == "float":
            if num_idx < len(cleaned_numbers):
                try:
                    # For interest rate, check if it's a percentage (divide by 100 if > 1)
                    val = float(cleaned_numbers[num_idx])
                    # If the value looks like a percentage (e.g., 5 for 5%), convert to decimal
                    if param_name == "interest_rate" and val > 1:
                        val = val / 100
                    params[param_name] = val
                    num_idx += 1
                except ValueError:
                    pass
        elif param_type == "string":
            # Check for enum values in the query
            if "enum" in param_info:
                enum_values = param_info["enum"]
                for enum_val in enum_values:
                    if enum_val.lower() in query.lower():
                        params[param_name] = enum_val
                        break
            # Only add if found (don't add default for optional params)
    
    return {func_name: params}
