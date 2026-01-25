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
    
    Uses regex to extract values - no LLM calls needed since values are explicit in text.
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
            # Extract array of numbers from the query
            # Look for patterns like: 1000, 2000, 3000 or 1000 2000 3000
            # First try to find comma-separated numbers
            numbers = re.findall(r'[\d,]+(?:\.\d+)?', query)
            
            # Clean up numbers (remove commas used as thousands separators vs delimiters)
            cleaned_numbers = []
            for num_str in numbers:
                # Remove commas and try to parse as float
                clean = num_str.replace(',', '')
                try:
                    cleaned_numbers.append(float(clean))
                except ValueError:
                    continue
            
            # Check items type
            items_type = param_info.get("items", {}).get("type", "float")
            if items_type in ["integer", "int"]:
                params[param_name] = [int(n) for n in cleaned_numbers]
            else:
                params[param_name] = cleaned_numbers
                
        elif param_type in ["integer", "int"]:
            # Extract single integer
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
                
        elif param_type in ["float", "number"]:
            # Extract single float
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                params[param_name] = float(numbers[0])
                
        elif param_type == "string":
            # Extract string value - look for quoted strings or after keywords
            quoted = re.search(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted.group(1)
            else:
                # Try to extract after common prepositions
                match = re.search(r'(?:for|in|of|with|named?)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|\.)|$)', query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
    
    return {func_name: params}
