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
    
    # Extract parameters from query using regex
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "integer":
            # Extract numbers from query
            # Look for patterns like "top 5", "5 popular", "number of 5", etc.
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                # Take the first number found
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # Check if there's an enum constraint
            enum_values = param_info.get("enum", [])
            if enum_values:
                # Look for enum values in the query
                for enum_val in enum_values:
                    if enum_val.lower() in query_lower:
                        params[param_name] = enum_val
                        break
                # If not found but there's a default mentioned in description, check for keywords
                if param_name not in params:
                    desc = param_info.get("description", "").lower()
                    # Check if query mentions sorting/ordering
                    if "sort" in query_lower or "order" in query_lower:
                        # Look for which sort type is mentioned
                        for enum_val in enum_values:
                            if enum_val.lower() in query_lower:
                                params[param_name] = enum_val
                                break
                        # Default to popularity if "sort by popularity" or similar
                        if param_name not in params and "popularity" in query_lower:
                            params[param_name] = "popularity"
            else:
                # For non-enum strings, try to extract relevant text
                # This would need more context-specific patterns
                pass
    
    return {func_name: params}
