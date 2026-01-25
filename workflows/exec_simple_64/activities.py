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
    """Extract function call parameters from user query using regex/parsing.
    
    Returns format: {"function_name": {"param1": val1, ...}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                first_item = question_data[0]
                if isinstance(first_item, list) and len(first_item) > 0:
                    query = first_item[0].get("content", str(prompt))
                elif isinstance(first_item, dict):
                    query = first_item.get("content", str(prompt))
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    # Get function details
    func = funcs[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema types
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract integers from query using regex
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                # Take the first number found
                params[param_name] = int(numbers[0])
        
        elif param_type == "float" or param_type == "number":
            # Extract floats/numbers
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
            if numbers:
                params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # For string params, try common patterns
            # Pattern: "for X", "of X", "in X", "with X"
            match = re.search(r'(?:for|of|in|with|named?)\s+([A-Za-z][A-Za-z\s]+?)(?:\s*[.,?!]|\s+(?:and|with|to|from)|$)', query, re.IGNORECASE)
            if match:
                params[param_name] = match.group(1).strip()
    
    return {func_name: params}
