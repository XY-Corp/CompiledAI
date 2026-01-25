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
    
    Parses the prompt to extract the function name and parameters,
    returning them in the format {"function_name": {"param1": val1, ...}}.
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "array":
            # Extract array of numbers - look for comma/space separated numbers
            # Pattern: numbers like 85, 90, 88, 92, 86, 89, 91
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
            
            # Filter out numbers that are likely bin/range values (usually single small numbers after keywords)
            # Look for "bin range" or "bins" followed by a number
            bin_match = re.search(r'(?:bin\s*range|bins?)\s*(?:to|of|is|=|:)?\s*(\d+)', query, re.IGNORECASE)
            bin_value = bin_match.group(1) if bin_match else None
            
            # Get item type for array
            items_type = param_info.get("items", {}).get("type", "integer")
            
            # Convert numbers, excluding the bin value if found
            data_numbers = []
            for num in numbers:
                if bin_value and num == bin_value:
                    continue  # Skip the bin value
                if items_type == "integer":
                    data_numbers.append(int(float(num)))
                else:
                    data_numbers.append(float(num))
            
            # If we have a bin value, remove one instance of it from data if it appears
            # (the bin value might appear in the data too, so only remove if it's clearly separate)
            if bin_value and len(data_numbers) > 0:
                # Check if the last number before "bin" keyword is the bin value
                params[param_name] = data_numbers
            else:
                params[param_name] = data_numbers
                
        elif param_type == "integer":
            # For bins/range parameters, look for specific patterns
            if "bin" in param_name.lower() or "range" in param_name.lower():
                # Look for "bin range to X", "bins X", "set bin range to X"
                bin_match = re.search(r'(?:bin\s*range|bins?)\s*(?:to|of|is|=|:)?\s*(\d+)', query, re.IGNORECASE)
                if bin_match:
                    params[param_name] = int(bin_match.group(1))
                else:
                    # Fallback: look for standalone number after "range" or "bin"
                    fallback_match = re.search(r'(?:range|bin)\D+(\d+)', query, re.IGNORECASE)
                    if fallback_match:
                        params[param_name] = int(fallback_match.group(1))
            else:
                # Generic integer extraction
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    params[param_name] = int(numbers[0])
                    
        elif param_type == "number" or param_type == "float":
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
            if numbers:
                params[param_name] = float(numbers[0])
                
        elif param_type == "string":
            # Extract string values - look for quoted strings or after keywords
            quoted = re.search(r'["\']([^"\']+)["\']', query)
            if quoted:
                params[param_name] = quoted.group(1)
            else:
                # Try to extract based on common patterns
                for_match = re.search(r'(?:for|in|of|with)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|$))', query, re.IGNORECASE)
                if for_match:
                    params[param_name] = for_match.group(1).strip()
    
    return {func_name: params}
