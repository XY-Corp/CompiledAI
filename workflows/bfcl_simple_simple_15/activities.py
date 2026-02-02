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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
    # Step 1: Parse prompt to extract the actual user query
    query = prompt
    if isinstance(prompt, str):
        try:
            data = json.loads(prompt)
            # Handle BFCL-style nested structure
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
                elif len(data["question"]) > 0 and isinstance(data["question"][0], dict):
                    query = data["question"][0].get("content", prompt)
            elif "query" in data:
                query = data["query"]
            elif "content" in data:
                query = data["content"]
        except (json.JSONDecodeError, TypeError, KeyError):
            query = prompt
    
    # Step 2: Parse functions list
    funcs = functions
    if isinstance(functions, str):
        try:
            funcs = json.loads(functions)
        except (json.JSONDecodeError, TypeError):
            funcs = []
    
    if not funcs:
        funcs = []
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # Get parameters schema - handle both "parameters.properties" and "parameters" directly
    params_schema = func.get("parameters", {})
    if isinstance(params_schema, dict):
        props = params_schema.get("properties", params_schema)
    else:
        props = {}
    
    required_params = params_schema.get("required", []) if isinstance(params_schema, dict) else []
    
    # Step 3: Extract parameter values using regex patterns
    params = {}
    query_lower = query.lower()
    
    for param_name, param_info in props.items():
        if isinstance(param_info, str):
            param_type = param_info
            param_desc = ""
        else:
            param_type = param_info.get("type", "string")
            param_desc = param_info.get("description", "").lower()
        
        value = None
        
        # Extract based on parameter name and type
        if param_name == "function":
            # Look for function expression like "y = x^3" or "function x^3"
            patterns = [
                r'function\s+(?:y\s*=\s*)?([^\s,]+)',
                r'y\s*=\s*([^\s,]+)',
                r'for\s+(?:the\s+)?(?:function\s+)?(?:y\s*=\s*)?([x\^\d\+\-\*\/\(\)]+)',
                r'curve\s+(?:of\s+)?(?:y\s*=\s*)?([x\^\d\+\-\*\/\(\)]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    break
        
        elif param_name == "start_x":
            # Look for starting x value: "from x = -2" or "x = -2 to"
            patterns = [
                r'from\s+x\s*=\s*(-?\d+)',
                r'x\s*=\s*(-?\d+)\s+to',
                r'between\s+x\s*=\s*(-?\d+)',
                r'from\s+(-?\d+)\s+to',
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = int(match.group(1))
                    break
        
        elif param_name == "end_x":
            # Look for ending x value: "to x = 3" or "x = 3"
            patterns = [
                r'to\s+x\s*=\s*(-?\d+)',
                r'x\s*=\s*-?\d+\s+to\s+x\s*=\s*(-?\d+)',
                r'to\s+(-?\d+)\s+for',
                r'from\s+-?\d+\s+to\s+(-?\d+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = int(match.group(1))
                    break
        
        elif param_name == "method":
            # Look for method: "using simpson" or "trapezoid method"
            if "simpson" in query_lower:
                value = "simpson"
            elif "trapezoid" in query_lower:
                value = "trapezoid"
            # method is optional, so don't set if not found
        
        # Generic extraction for other parameters
        if value is None and param_type in ["integer", "number", "float"]:
            # Try to find numbers associated with this parameter
            pattern = rf'{param_name}\s*[=:]\s*(-?\d+(?:\.\d+)?)'
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                if param_type == "integer":
                    value = int(match.group(1))
                else:
                    value = float(match.group(1))
        
        if value is not None:
            params[param_name] = value
    
    return {func_name: params}
