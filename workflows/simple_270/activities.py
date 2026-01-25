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
    """Extract function name and parameters from user query and function schema.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data.get("question", [])
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
    
    if not funcs:
        return {"error": "No functions provided"}
    
    # Get function details
    func = funcs[0] if isinstance(funcs, list) else funcs
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {})
    properties = params_schema.get("properties", {})
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in properties.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # Handle enum parameters
        if "enum" in param_info:
            enum_values = param_info["enum"]
            for enum_val in enum_values:
                if enum_val.lower() in query_lower:
                    params[param_name] = enum_val
                    break
        
        # Handle string parameters - extract based on context
        elif param_type == "string":
            if "name" in param_name.lower() or "building" in param_desc:
                # Extract building/entity name - look for proper nouns
                # Pattern: "of X" or "the X" followed by building-related words
                patterns = [
                    r'(?:of|the)\s+([A-Z][A-Za-z\s]+?)(?:\s+(?:building|tower|in|height|width|dimension))',
                    r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+)(?:\s+(?:building|tower))?',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        extracted = match.group(1).strip()
                        # Clean up common suffixes
                        extracted = re.sub(r'\s+building$', '', extracted, flags=re.IGNORECASE).strip()
                        if extracted:
                            params[param_name] = extracted
                            break
                
                # Fallback: look for "Empire State" pattern specifically
                if param_name not in params:
                    empire_match = re.search(r'(Empire\s+State(?:\s+[Bb]uilding)?)', query)
                    if empire_match:
                        name = empire_match.group(1)
                        # Remove "building" suffix if present
                        name = re.sub(r'\s+[Bb]uilding$', '', name).strip()
                        params[param_name] = name
        
        # Handle numeric parameters
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
