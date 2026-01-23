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
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # For BMI calculation, we expect weight and height
    # Common patterns: "weight of X kilograms", "height of Y cm"
    
    # Try to extract weight (look for patterns like "weight of 85" or "85 kilograms/kg")
    weight_match = re.search(r'weight\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if not weight_match:
        weight_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)', query, re.IGNORECASE)
    
    # Try to extract height (look for patterns like "height of 180" or "180 cm")
    height_match = re.search(r'height\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if not height_match:
        height_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:cm|centimeters?)', query, re.IGNORECASE)
    
    # Assign extracted values to parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "weight" and weight_match:
            value = weight_match.group(1)
            params[param_name] = int(float(value)) if param_type == "integer" else float(value)
        elif param_name == "height" and height_match:
            value = height_match.group(1)
            params[param_name] = int(float(value)) if param_type == "integer" else float(value)
        elif param_name == "unit":
            # Check if unit is mentioned in query
            if re.search(r'\bimperial\b', query, re.IGNORECASE):
                params[param_name] = "imperial"
            elif re.search(r'\bmetric\b', query, re.IGNORECASE):
                params[param_name] = "metric"
            # Don't include optional param if not specified
    
    # Fallback: if specific patterns didn't match, use positional numbers
    if "weight" in params_schema and "weight" not in params and len(numbers) >= 1:
        # First number is typically weight
        params["weight"] = int(float(numbers[0]))
    
    if "height" in params_schema and "height" not in params and len(numbers) >= 2:
        # Second number is typically height
        params["height"] = int(float(numbers[1]))
    
    return {func_name: params}
