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
    """Extract function name and parameters from user query using regex/parsing."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data.get("question", [[]])
            if isinstance(question_data, list) and len(question_data) > 0:
                first_item = question_data[0]
                if isinstance(first_item, list) and len(first_item) > 0:
                    query = first_item[0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            # Extract list from query - look for [...]
            list_match = re.search(r'\[([^\]]+)\]', query)
            if list_match:
                list_content = list_match.group(1)
                # Parse numbers from the list
                numbers = re.findall(r'-?\d+(?:\.\d+)?', list_content)
                # Convert to appropriate type based on items type
                items_type = param_info.get("items", {}).get("type", "float")
                if items_type in ["float", "number"]:
                    params[param_name] = [float(n) for n in numbers]
                elif items_type == "integer":
                    params[param_name] = [int(float(n)) for n in numbers]
                else:
                    params[param_name] = [float(n) for n in numbers]
        
        elif param_type == "string":
            # Check if it's an enum
            enum_values = param_info.get("enum", [])
            if enum_values:
                # Look for enum value in query
                query_lower = query.lower()
                for enum_val in enum_values:
                    if enum_val.lower() in query_lower:
                        params[param_name] = enum_val
                        break
                # Default to first enum if not found but required
                if param_name not in params and enum_values:
                    # Check context clues
                    if "ascending" in query_lower or "asc" in query_lower:
                        params[param_name] = "ascending"
                    elif "descending" in query_lower or "desc" in query_lower:
                        params[param_name] = "descending"
                    else:
                        # Default based on common patterns
                        params[param_name] = enum_values[0]
            else:
                # Extract string value - look for quoted strings or after keywords
                string_match = re.search(r'"([^"]+)"', query)
                if string_match:
                    params[param_name] = string_match.group(1)
        
        elif param_type in ["integer", "number", "float"]:
            # Extract single number
            numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
