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
    """Extract function name and parameters from user query using regex patterns."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
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
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers (integers and floats) from the query
    # Pattern matches: 4, 0.01, 4.5, etc.
    numbers = re.findall(r'\d+\.?\d*', query)
    float_numbers = [float(n) for n in numbers]
    
    # Map extracted values to parameters based on schema
    number_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["float", "number"]:
            # Look for float values - typically charge values are small decimals
            # Find the number that looks like a charge (small decimal like 0.01)
            for num in float_numbers:
                if num < 1 and num > 0:  # Likely a charge value in Coulombs
                    params[param_name] = num
                    break
            else:
                # Fallback: use first available number
                if number_idx < len(float_numbers):
                    params[param_name] = float_numbers[number_idx]
                    number_idx += 1
                    
        elif param_type == "integer":
            # Look for integer values - typically distance values are whole numbers
            # Pattern: "X meters" or "X m"
            distance_match = re.search(r'(\d+)\s*(?:meters?|m\b)', query, re.IGNORECASE)
            if distance_match:
                params[param_name] = int(distance_match.group(1))
            else:
                # Find whole numbers that aren't part of decimals
                for num in float_numbers:
                    if num == int(num) and num >= 1:  # Whole number, likely distance
                        params[param_name] = int(num)
                        break
                        
        elif param_type == "string":
            # For medium parameter - check if mentioned in query
            # Common mediums: vacuum, air, water, glass, etc.
            medium_match = re.search(r'\b(vacuum|air|water|glass|oil)\b', query, re.IGNORECASE)
            if medium_match:
                params[param_name] = medium_match.group(1).lower()
            # Don't include optional string params if not found in query
    
    return {func_name: params}
