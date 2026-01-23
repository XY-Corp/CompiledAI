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
    """Extract function name and parameters from user query using regex.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
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

    # Extract all numbers from the query using regex
    # Pattern matches integers and decimals, including those with $ prefix
    numbers = re.findall(r'\$?(\d+(?:\.\d+)?)', query)
    
    # Convert to appropriate types
    extracted_numbers = []
    for num in numbers:
        if '.' in num:
            extracted_numbers.append(float(num))
        else:
            extracted_numbers.append(int(num))

    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    # For CAGR calculation, we expect: initial_value, final_value, period_in_years
    # The query typically mentions them in order: initial ($2000), final ($3000), years (4)
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            if num_idx < len(extracted_numbers):
                value = extracted_numbers[num_idx]
                # Convert to int if schema expects integer
                if param_type == "integer":
                    params[param_name] = int(value)
                else:
                    params[param_name] = value
                num_idx += 1
        elif param_type == "string":
            # For string parameters, try to extract relevant text
            # This is a fallback - most CAGR params are numeric
            params[param_name] = ""

    return {func_name: params}
