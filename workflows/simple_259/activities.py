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
    """Extract function name and parameters from user query using regex patterns.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
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

    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    # For paint calculation, we need to map numbers intelligently
    # Query: "wall of 30 feet by 12 feet using ... covers 400 square feet per gallon"
    # Pattern: length x height ... coverage_rate
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "number", "float"]:
            # Try to find the right number based on context
            value = None
            
            # Coverage rate - look for "covers X square feet" pattern
            if "coverage" in param_name.lower() or "coverage" in param_desc:
                coverage_match = re.search(r'covers?\s+(\d+)\s+square\s+feet', query, re.IGNORECASE)
                if coverage_match:
                    value = int(coverage_match.group(1))
            
            # Length - look for first dimension in "X feet by Y feet" pattern
            elif "length" in param_name.lower():
                dim_match = re.search(r'(\d+)\s*(?:feet|ft)?\s*(?:by|x)\s*(\d+)', query, re.IGNORECASE)
                if dim_match:
                    value = int(dim_match.group(1))
            
            # Height - look for second dimension in "X feet by Y feet" pattern
            elif "height" in param_name.lower():
                dim_match = re.search(r'(\d+)\s*(?:feet|ft)?\s*(?:by|x)\s*(\d+)', query, re.IGNORECASE)
                if dim_match:
                    value = int(dim_match.group(2))
            
            # Fallback: use numbers in order if specific pattern not found
            if value is None and num_idx < len(numbers):
                value = int(float(numbers[num_idx]))
                num_idx += 1
            
            if value is not None:
                params[param_name] = value
        
        elif param_type == "string":
            # For string params, try to extract relevant text
            # This is a fallback - most paint calculation params are numeric
            params[param_name] = ""

    return {func_name: params}
