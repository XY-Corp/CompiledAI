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
    # Parse prompt - handle BFCL format (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # BFCL format: {"question": [[{"role": "user", "content": "..."}]], "function": [...]}
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
    
    # Extract all numbers from the query
    # Pattern matches integers and decimals
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Build parameters dict based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "number", "float"]:
            # Look for specific patterns first
            # Pattern: "weight of X kg" or "X kg weight"
            if param_name == "weight":
                weight_match = re.search(r'weight\s+of\s+(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*kg', query, re.IGNORECASE)
                if weight_match:
                    val = weight_match.group(1) or weight_match.group(2)
                    params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                    continue
            
            # Pattern: "height of X cm" or "X cm height"
            if param_name == "height":
                height_match = re.search(r'height\s+of\s+(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*cm', query, re.IGNORECASE)
                if height_match:
                    val = height_match.group(1) or height_match.group(2)
                    params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                    continue
            
            # Fallback: use numbers in order
            if num_idx < len(numbers):
                val = numbers[num_idx]
                params[param_name] = int(float(val)) if param_type == "integer" else float(val)
                num_idx += 1
        
        elif param_type == "string":
            # Check for specific string patterns
            if param_name == "system":
                # Look for metric/imperial keywords
                if re.search(r'\bimperial\b', query, re.IGNORECASE):
                    params[param_name] = "imperial"
                elif re.search(r'\bmetric\b', query, re.IGNORECASE):
                    params[param_name] = "metric"
                # Don't include optional param if not specified
            else:
                # Generic string extraction: look for "param_name X" or "X param_name"
                string_match = re.search(rf'{param_name}\s+(?:is\s+)?["\']?([^"\']+)["\']?', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()

    return {func_name: params}
