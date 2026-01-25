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
    """Extract function call parameters from natural language prompt.
    
    Parses the user query and function schema to extract parameter values
    using regex and string matching - no LLM calls needed.
    """
    # Parse prompt (may be JSON string with nested structure)
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
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameter values from query
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    number_idx = 0
    
    # Extract color - common color words
    color_pattern = r'\b(red|blue|green|yellow|black|white|orange|purple|pink|brown|gray|grey|cyan|magenta)\b'
    color_match = re.search(color_pattern, query, re.IGNORECASE)
    
    # Map extracted values to parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer":
            # Try to match number contextually based on param name
            # Look for patterns like "width of 20" or "20 units wide"
            width_pattern = r'width\s+(?:of\s+)?(\d+)|(\d+)\s*(?:units?\s+)?(?:wide|width)'
            height_pattern = r'height\s+(?:of\s+)?(\d+)|(\d+)\s*(?:units?\s+)?(?:high|height|tall)'
            
            if param_name == "width" or "width" in param_desc:
                width_match = re.search(width_pattern, query, re.IGNORECASE)
                if width_match:
                    val = width_match.group(1) or width_match.group(2)
                    params[param_name] = int(val)
                elif number_idx < len(numbers):
                    params[param_name] = int(float(numbers[number_idx]))
                    number_idx += 1
            elif param_name == "height" or "height" in param_desc:
                height_match = re.search(height_pattern, query, re.IGNORECASE)
                if height_match:
                    val = height_match.group(1) or height_match.group(2)
                    params[param_name] = int(val)
                elif number_idx < len(numbers):
                    params[param_name] = int(float(numbers[number_idx]))
                    number_idx += 1
            elif number_idx < len(numbers):
                params[param_name] = int(float(numbers[number_idx]))
                number_idx += 1
                
        elif param_type == "number" or param_type == "float":
            if number_idx < len(numbers):
                params[param_name] = float(numbers[number_idx])
                number_idx += 1
                
        elif param_type == "string":
            if param_name == "color" or "color" in param_desc:
                if color_match:
                    params[param_name] = color_match.group(1).lower()
            else:
                # Try to extract quoted strings or named values
                quoted_match = re.search(r'"([^"]+)"', query)
                if quoted_match:
                    params[param_name] = quoted_match.group(1)
    
    return {func_name: params}
