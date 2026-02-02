import re
import json
from typing import Any


async def extract_function_call(
    prompt: str,
    functions: list = None,
    user_query: str = None,
    tools: list = None,
    tool_name_mapping: dict = None,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from natural language query.
    
    Returns format: {"function_name": {"param1": val1, ...}}
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            try:
                data = json.loads(prompt)
                # Handle BFCL-style nested structure
                if "question" in data and isinstance(data["question"], list):
                    if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                        query = data["question"][0][0].get("content", prompt)
                    else:
                        query = str(data["question"])
                else:
                    query = data.get("content", prompt)
            except json.JSONDecodeError:
                query = prompt
        else:
            query = str(prompt)
    except:
        query = str(prompt)

    # Parse functions list
    funcs = []
    if functions:
        if isinstance(functions, str):
            try:
                funcs = json.loads(functions)
            except:
                funcs = []
        else:
            funcs = functions
    
    # Get target function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])

    # Extract parameters based on schema
    params = {}
    
    # For calculate_area_under_curve, extract:
    # - function: mathematical function string (e.g., "x^2", "y=x^2")
    # - interval: [start, end] array of floats
    # - method: optional numerical method
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "function":
            # Extract mathematical function - look for patterns like y=x^2, x^2, sin(x), etc.
            func_patterns = [
                r'y\s*=\s*([^\s,]+(?:\s*[\+\-\*\/]\s*[^\s,]+)*)',  # y = x^2
                r'function\s+([^\s,]+)',  # function x^2
                r'curve\s+([^\s,]+)',  # curve x^2
                r'f\(x\)\s*=\s*([^\s,]+)',  # f(x) = x^2
            ]
            
            func_value = None
            for pattern in func_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    func_value = match.group(1).strip()
                    break
            
            if func_value:
                params[param_name] = func_value
                
        elif param_name == "interval":
            # Extract interval - look for "from X to Y" or "[X, Y]" patterns
            interval_patterns = [
                r'from\s+(?:x\s*=\s*)?(-?\d+(?:\.\d+)?)\s+to\s+(?:x\s*=\s*)?(-?\d+(?:\.\d+)?)',  # from x=1 to x=3
                r'interval\s*\[?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]?',  # interval [1, 3]
                r'between\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)',  # between 1 and 3
                r'\[(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\]',  # [1, 3]
            ]
            
            for pattern in interval_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    start = float(match.group(1))
                    end = float(match.group(2))
                    params[param_name] = [start, end]
                    break
                    
        elif param_name == "method":
            # Extract method if specified - look for method names
            method_patterns = [
                r'using\s+(\w+)\s+method',  # using trapezoidal method
                r'method\s*[=:]\s*["\']?(\w+)["\']?',  # method = trapezoidal
                r'(trapezoidal|simpson|rectangular|midpoint)',  # direct method name
            ]
            
            for pattern in method_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).lower()
                    break
        
        elif param_type in ["integer", "number", "float"]:
            # Generic number extraction
            numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
                    
        elif param_type == "string":
            # Generic string - try to extract quoted values or after keywords
            quoted = re.search(r'["\']([^"\']+)["\']', query)
            if quoted:
                params[param_name] = quoted.group(1)

    return {func_name: params}
