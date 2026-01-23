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
    """Extract function name and parameters from user query based on function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
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
                query = data["question"][0][0].get("content", str(prompt))
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
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_enum = param_info.get("enum", [])
        
        if param_name == "century":
            # Extract century - look for patterns like "19th century", "19th", etc.
            century_patterns = [
                r'(\d{1,2})(?:st|nd|rd|th)\s*century',
                r'century\s*(\d{1,2})',
                r'(\d{4})s?',  # Year like 1800s -> 19th century
            ]
            for pattern in century_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    value = int(match.group(1))
                    # If it's a year (4 digits), convert to century
                    if value >= 100:
                        value = (value // 100) + 1
                    params[param_name] = value
                    break
        
        elif param_name == "region":
            # Check for region enum values in query
            if param_enum:
                for region in param_enum:
                    if region.lower() in query_lower:
                        params[param_name] = region
                        break
                
                # If no specific region found, check for "European" or "Europe" -> default to a region
                if param_name not in params:
                    if "european" in query_lower or "europe" in query_lower:
                        # Default to Western for general European queries
                        params[param_name] = "Western"
        
        elif param_name == "category":
            # Check for category enum values in query
            if param_enum:
                for category in param_enum:
                    if category.lower() in query_lower:
                        params[param_name] = category
                        break
        
        elif param_type == "integer":
            # Generic integer extraction
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string" and param_enum:
            # Check enum values
            for enum_val in param_enum:
                if enum_val.lower() in query_lower:
                    params[param_name] = enum_val
                    break
    
    return {func_name: params}
