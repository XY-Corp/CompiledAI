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
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Build parameters dict by matching numbers to parameter names
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            if num_idx < len(numbers):
                # Try to match number contextually based on param name
                value = None
                
                # Look for contextual patterns like "base of 10" or "height of 5"
                pattern = rf'{param_name}\s*(?:of|is|=|:)?\s*(\d+(?:\.\d+)?)'
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1)
                
                # If no contextual match, use numbers in order
                if value is None:
                    value = numbers[num_idx]
                    num_idx += 1
                else:
                    # Remove used number from list to avoid reuse
                    if value in numbers:
                        numbers.remove(value)
                
                # Convert to appropriate type
                if param_type == "integer":
                    params[param_name] = int(float(value))
                else:
                    params[param_name] = float(value)
    
    return {func_name: params}
