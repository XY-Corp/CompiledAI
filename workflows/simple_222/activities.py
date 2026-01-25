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
    """Extract function name and parameters from user query using regex patterns.
    
    Returns format: {"function_name": {"param1": val1, "param2": val2}}
    """
    # Parse prompt - handle BFCL format (may be JSON string)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from nested BFCL structure
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
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
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Track which numbers we've used
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "number", "float"]:
            # Try to find a number associated with this parameter
            # Look for patterns like "weight is 70" or "70 kg" based on description
            
            # Check for specific patterns based on param name/description
            value_found = False
            
            if "weight" in param_name.lower() or "weight" in param_desc:
                # Look for weight patterns: "weight is 70", "70 kg", "70 kilograms"
                weight_patterns = [
                    r'weight\s+(?:is\s+)?(\d+(?:\.\d+)?)',
                    r'(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)',
                ]
                for pattern in weight_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        val = match.group(1)
                        params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                        value_found = True
                        break
            
            elif "height" in param_name.lower() or "height" in param_desc:
                # Look for height patterns: "height is 180", "180 cm", "180 centimeters"
                height_patterns = [
                    r'height\s+(?:is\s+)?(\d+(?:\.\d+)?)',
                    r'(\d+(?:\.\d+)?)\s*(?:cm|centimeters?)',
                ]
                for pattern in height_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        val = match.group(1)
                        params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                        value_found = True
                        break
            
            # Fallback: use numbers in order if not found by pattern
            if not value_found and num_idx < len(numbers):
                val = numbers[num_idx]
                params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                num_idx += 1
        
        elif param_type == "string":
            # For string parameters, look for specific patterns
            # Check if it's a unit parameter
            if "unit" in param_name.lower() or "system" in param_desc:
                # Look for metric/imperial mentions
                if re.search(r'\b(metric|kg|cm|kilograms?|centimeters?)\b', query, re.IGNORECASE):
                    params[param_name] = "metric"
                elif re.search(r'\b(imperial|lbs?|pounds?|feet|inches?|ft|in)\b', query, re.IGNORECASE):
                    params[param_name] = "imperial"
                # Don't set if not mentioned (optional parameter)
            else:
                # Generic string extraction - look for quoted strings or named values
                string_match = re.search(r'(?:for|in|of|with|named?)\s+["\']?([A-Za-z\s]+)["\']?', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()

    return {func_name: params}
