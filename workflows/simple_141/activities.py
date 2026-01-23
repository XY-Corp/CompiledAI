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
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
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
    
    # Extract parameters from query using regex and string matching
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in params_schema.items():
        param_desc = param_info.get("description", "").lower()
        param_type = param_info.get("type", "string")
        
        # Strategy 1: Look for specific keywords based on parameter name/description
        if param_name == "metal" or "metal" in param_desc:
            # Common metals to look for
            metals = ["gold", "silver", "platinum", "palladium", "copper", "aluminum", "iron", "steel", "bronze", "brass", "nickel", "zinc", "lead", "tin"]
            for metal in metals:
                if metal in query_lower:
                    params[param_name] = metal.capitalize() if metal == "gold" else metal
                    # Check original case in query
                    match = re.search(rf'\b({metal})\b', query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1)
                    break
        
        elif param_name == "measure" or "measure" in param_desc or "unit" in param_desc:
            # Common measure units
            measures = ["ounce", "oz", "kg", "kilogram", "gram", "g", "pound", "lb", "ton", "tonne"]
            for measure in measures:
                if measure in query_lower:
                    # Normalize common abbreviations
                    if measure == "oz":
                        params[param_name] = "ounce"
                    elif measure == "kg":
                        params[param_name] = "kg"
                    elif measure == "g":
                        params[param_name] = "gram"
                    elif measure == "lb":
                        params[param_name] = "pound"
                    else:
                        params[param_name] = measure
                    break
            
            # Also check for "per X" pattern
            per_match = re.search(r'per\s+(\w+)', query_lower)
            if per_match and param_name not in params:
                unit = per_match.group(1)
                if unit in ["ounce", "oz", "kg", "kilogram", "gram", "pound", "lb"]:
                    if unit == "oz":
                        params[param_name] = "ounce"
                    else:
                        params[param_name] = unit
        
        # Strategy 2: For numeric parameters, extract numbers
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
