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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Uses regex and JSON parsing to extract values - no LLM calls needed.
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
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
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
            # Extract array of numbers from query
            # Look for patterns like [12, 15, 18, 20, 21, 26, 30] or "12, 15, 18, 20"
            
            # First try to find a bracketed list
            bracket_match = re.search(r'\[([^\]]+)\]', query)
            if bracket_match:
                array_content = bracket_match.group(1)
                # Extract all numbers from the bracketed content
                numbers = re.findall(r'-?\d+(?:\.\d+)?', array_content)
                
                # Determine item type
                items_type = param_info.get("items", {}).get("type", "float")
                if items_type in ["integer", "int"]:
                    params[param_name] = [int(n) for n in numbers]
                else:
                    params[param_name] = [float(n) for n in numbers]
            else:
                # Try to find comma-separated numbers
                numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
                if numbers:
                    items_type = param_info.get("items", {}).get("type", "float")
                    if items_type in ["integer", "int"]:
                        params[param_name] = [int(n) for n in numbers]
                    else:
                        params[param_name] = [float(n) for n in numbers]
        
        elif param_type in ["integer", "int"]:
            # Extract single integer
            numbers = re.findall(r'-?\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type in ["number", "float"]:
            # Extract single number
            numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
            if numbers:
                params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Extract string value - look for quoted strings or after keywords
            quoted_match = re.search(r'"([^"]+)"', query)
            if quoted_match:
                params[param_name] = quoted_match.group(1)
            else:
                # Try to extract after common prepositions
                prep_match = re.search(r'(?:for|in|of|with|named?)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|\.)|$)', query, re.IGNORECASE)
                if prep_match:
                    params[param_name] = prep_match.group(1).strip()
    
    return {func_name: params}
