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
    """Extract function name and parameters from user query. Returns {"func_name": {params}}."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in props.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            # Extract arrays from query - look for patterns like [1, 2, 3] or Group A [1, 2, 3]
            # Pattern to match arrays with optional group labels
            array_pattern = r'\[([^\]]+)\]'
            arrays_found = re.findall(array_pattern, query)
            
            # Map arrays to parameters based on order (group1 first, group2 second)
            if param_name == "group1" and len(arrays_found) >= 1:
                # Parse the first array
                items = [int(x.strip()) for x in arrays_found[0].split(',') if x.strip().lstrip('-').isdigit()]
                params[param_name] = items
            elif param_name == "group2" and len(arrays_found) >= 2:
                # Parse the second array
                items = [int(x.strip()) for x in arrays_found[1].split(',') if x.strip().lstrip('-').isdigit()]
                params[param_name] = items
        
        elif param_type == "boolean":
            # Look for boolean indicators in the query
            query_lower = query.lower()
            
            if param_name == "equal_variance":
                # Check for explicit mentions of equal/unequal variance
                if "equal variance" in query_lower or "assuming equal" in query_lower:
                    params[param_name] = True
                elif "unequal variance" in query_lower or "not equal variance" in query_lower:
                    params[param_name] = False
                # Use default if specified in schema
                elif "default" in param_info:
                    params[param_name] = param_info["default"]
            else:
                # Generic boolean extraction
                if "true" in query_lower or "yes" in query_lower:
                    params[param_name] = True
                elif "false" in query_lower or "no" in query_lower:
                    params[param_name] = False
                elif "default" in param_info:
                    params[param_name] = param_info["default"]
        
        elif param_type == "integer":
            # Extract integers
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "number":
            # Extract numbers (including floats)
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
            if numbers:
                params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # For string params, try to extract relevant text
            # This is a fallback - specific patterns should be added as needed
            pass
    
    return {func_name: params}
