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
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_type == "integer" or param_type == "number":
            # Extract numbers based on context from description
            if "weight" in param_name.lower() or "weight" in param_desc:
                # Look for weight pattern: "weight is X kg" or "X kg"
                weight_patterns = [
                    r'weight\s+(?:is\s+)?(\d+(?:\.\d+)?)\s*(?:kg|kilogram)',
                    r'(\d+(?:\.\d+)?)\s*(?:kg|kilogram).*weight',
                    r'(\d+(?:\.\d+)?)\s*kg\b',
                ]
                for pattern in weight_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        val = float(match.group(1))
                        params[param_name] = int(val) if param_type == "integer" else val
                        break
                        
            elif "height" in param_name.lower() or "height" in param_desc:
                # Look for height pattern: "height is X cm" or "X cm"
                height_patterns = [
                    r'height\s+(?:is\s+)?(\d+(?:\.\d+)?)\s*(?:cm|centimeter)',
                    r'(\d+(?:\.\d+)?)\s*(?:cm|centimeter).*height',
                    r'(\d+(?:\.\d+)?)\s*cm\b',
                ]
                for pattern in height_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        val = float(match.group(1))
                        params[param_name] = int(val) if param_type == "integer" else val
                        break
            else:
                # Generic number extraction - find all numbers and assign in order
                numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
                # Try to match based on position in schema
                param_names = list(params_schema.keys())
                idx = param_names.index(param_name)
                numeric_params = [p for p in param_names[:idx+1] 
                                  if params_schema[p].get("type") in ["integer", "number"]]
                num_idx = len(numeric_params) - 1
                if num_idx < len(numbers):
                    val = float(numbers[num_idx])
                    params[param_name] = int(val) if param_type == "integer" else val
                    
        elif param_type == "string":
            # Check if this is an optional parameter with a default
            # Only include if explicitly mentioned in query
            if "unit" in param_name.lower():
                # Look for unit specification
                unit_patterns = [
                    r'\b(metric|imperial|standard)\b',
                    r'in\s+(metric|imperial)\s+(?:system|units?)?',
                ]
                for pattern in unit_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = match.group(1).lower()
                        break
                # Don't include optional unit if not specified
            else:
                # Generic string extraction based on context
                pass

    return {func_name: params}
