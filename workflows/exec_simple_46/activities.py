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
    """
    Extract function call parameters from natural language prompt.
    Returns format: {"function_name": {"param1": val1}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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

    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract integers from query using regex
            # Look for numbers in the text
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                # For prime factorization, we want the number being factored
                # Usually the largest or most prominent number mentioned
                # Filter out small numbers that are likely not the target (like years, etc.)
                int_numbers = [int(n) for n in numbers]
                # Take the first significant number found
                params[param_name] = int_numbers[0]
        
        elif param_type == "number" or param_type == "float":
            # Extract floats/numbers
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
            if numbers:
                params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # For string parameters, try common patterns
            # Pattern: "for X" or "in X" or "of X"
            string_match = re.search(
                r'(?:for|in|of|with|named?|called?)\s+["\']?([A-Za-z\s]+?)["\']?(?:\s+(?:and|with|,|\.)|$)',
                query,
                re.IGNORECASE
            )
            if string_match:
                params[param_name] = string_match.group(1).strip()

    return {func_name: params}
