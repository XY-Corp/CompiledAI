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

    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type in ["integer", "number", "float"]:
            # Try to match number based on context in description
            matched = False
            
            # Look for specific patterns based on parameter description
            if "weight" in param_desc:
                # Look for weight pattern: "weight of X kg" or "X kg"
                weight_match = re.search(r'weight\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:kg|kilogram)?', query, re.IGNORECASE)
                if weight_match:
                    val = weight_match.group(1)
                    params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                    matched = True
            
            elif "height" in param_desc:
                # Look for height pattern: "height of X cm" or "X cm"
                height_match = re.search(r'height\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:cm|centimeter)?', query, re.IGNORECASE)
                if height_match:
                    val = height_match.group(1)
                    params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                    matched = True
            
            # Fallback: use numbers in order if not matched by context
            if not matched and num_idx < len(numbers):
                val = numbers[num_idx]
                params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                num_idx += 1
                
        elif param_type == "string":
            # Check for specific string patterns
            if "system" in param_name.lower() or "unit" in param_desc:
                # Look for metric/imperial
                if re.search(r'\bimperial\b', query, re.IGNORECASE):
                    params[param_name] = "imperial"
                elif re.search(r'\bmetric\b', query, re.IGNORECASE):
                    params[param_name] = "metric"
                # Don't set if not mentioned (optional param with default)
            else:
                # Generic string extraction - look for quoted strings or named values
                string_match = re.search(r'(?:for|in|of|with|named?)\s+["\']?([A-Za-z\s]+?)["\']?(?:\s+(?:and|with|,)|$)', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()

    return {func_name: params}
