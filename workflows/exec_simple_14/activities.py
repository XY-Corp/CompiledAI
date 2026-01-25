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
    """Extract function call parameters from natural language query.
    
    Parses the user query to identify the function to call and extracts
    the required parameters using regex and string parsing.
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            items_type = param_info.get("items", {}).get("type", "string")
            
            if items_type in ["float", "number", "integer"]:
                # Look for range patterns like "from X to Y" or "ranging from X to Y"
                range_pattern = r'(?:from|ranging from)\s+(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)'
                range_match = re.search(range_pattern, query, re.IGNORECASE)
                
                # Look for increment pattern like "incrementing by X" or "by X each"
                increment_pattern = r'(?:increment(?:ing)?|by)\s+(\d+(?:\.\d+)?)\s*(?:each|every)?'
                increment_match = re.search(increment_pattern, query, re.IGNORECASE)
                
                if range_match:
                    start = float(range_match.group(1))
                    end = float(range_match.group(2))
                    
                    # Default increment is 1, but check for specified increment
                    increment = 1.0
                    if increment_match:
                        increment = float(increment_match.group(1))
                    
                    # Generate the list of numbers
                    numbers = []
                    current = start
                    while current <= end:
                        if items_type == "integer":
                            numbers.append(int(current))
                        else:
                            numbers.append(float(current))
                        current += increment
                    
                    params[param_name] = numbers
                else:
                    # Fallback: extract all numbers from the query
                    all_numbers = re.findall(r'\d+(?:\.\d+)?', query)
                    if items_type == "integer":
                        params[param_name] = [int(float(n)) for n in all_numbers]
                    else:
                        params[param_name] = [float(n) for n in all_numbers]
            else:
                # String array - extract quoted strings or comma-separated values
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted
                else:
                    params[param_name] = []
        
        elif param_type in ["integer", "number", "float"]:
            # Extract single number
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Extract string value - look for patterns like "for X" or "in X"
            string_match = re.search(r'(?:for|in|of|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,)|$)', query, re.IGNORECASE)
            if string_match:
                params[param_name] = string_match.group(1).strip()
            else:
                params[param_name] = ""
    
    return {func_name: params}
