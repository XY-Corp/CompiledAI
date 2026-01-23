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
    
    Returns format: {"function_name": {"param1": val1}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question = data["question"]
            if isinstance(question, list) and len(question) > 0:
                if isinstance(question[0], list) and len(question[0]) > 0:
                    query = question[0][0].get("content", str(prompt))
                else:
                    query = str(question[0])
            else:
                query = str(question)
        else:
            query = str(data)
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
    
    # Extract parameter values using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    num_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            if num_idx < len(numbers):
                params[param_name] = int(numbers[num_idx])
                num_idx += 1
        elif param_type in ["number", "float"]:
            if num_idx < len(numbers):
                params[param_name] = float(numbers[num_idx])
                num_idx += 1
        elif param_type == "string":
            # Try to extract string values using common patterns
            # Pattern: "for X" or "in X" or "of X" or "with X"
            string_match = re.search(
                r'(?:for|in|of|with|named?)\s+([A-Za-z][A-Za-z\s]*?)(?:\s+(?:and|with|,|$))',
                query,
                re.IGNORECASE
            )
            if string_match:
                params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
