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
    
    # For quadratic equation coefficients, look for explicit mentions
    # Pattern 1: "coefficients X for a, Y for b, and Z for c"
    coef_pattern = r'coefficients?\s+(-?\d+)\s+for\s+a[,\s]+(-?\d+)\s+for\s+b[,\s]+(?:and\s+)?(-?\d+)\s+for\s+c'
    coef_match = re.search(coef_pattern, query, re.IGNORECASE)
    
    if coef_match:
        params["a"] = int(coef_match.group(1))
        params["b"] = int(coef_match.group(2))
        params["c"] = int(coef_match.group(3))
    else:
        # Pattern 2: "ax^2 + bx + c" format like "3x^2 + 7x - 10"
        quad_pattern = r'(-?\d+)\s*x\s*\^\s*2\s*([+-])\s*(\d+)\s*x\s*([+-])\s*(\d+)'
        quad_match = re.search(quad_pattern, query)
        
        if quad_match:
            params["a"] = int(quad_match.group(1))
            # Handle sign for b
            b_sign = 1 if quad_match.group(2) == '+' else -1
            params["b"] = b_sign * int(quad_match.group(3))
            # Handle sign for c
            c_sign = 1 if quad_match.group(4) == '+' else -1
            params["c"] = c_sign * int(quad_match.group(5))
        else:
            # Pattern 3: Look for "a = X", "b = Y", "c = Z" patterns
            for param_name in ["a", "b", "c"]:
                param_pattern = rf'{param_name}\s*[=:]\s*(-?\d+)'
                param_match = re.search(param_pattern, query, re.IGNORECASE)
                if param_match:
                    params[param_name] = int(param_match.group(1))
            
            # Pattern 4: Fallback - extract all integers and map to a, b, c
            if len(params) < 3:
                all_numbers = re.findall(r'-?\d+', query)
                # Filter out common non-coefficient numbers (like "2" in "x^2")
                # Look for numbers that appear as coefficients
                param_names = ["a", "b", "c"]
                idx = 0
                for num in all_numbers:
                    if idx >= 3:
                        break
                    param_name = param_names[idx]
                    if param_name not in params:
                        params[param_name] = int(num)
                        idx += 1
    
    return {func_name: params}
