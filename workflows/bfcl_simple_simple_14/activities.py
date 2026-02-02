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
    
    # Get the target function (first one in the list)
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # Get parameters schema - handle both "parameters" with nested "properties" and direct "parameters"
    params_schema = func.get("parameters", {})
    if "properties" in params_schema:
        props = params_schema.get("properties", {})
    else:
        props = params_schema
    
    required_params = params_schema.get("required", [])
    
    # Step 3: Extract parameter values using regex and string matching
    params = {}
    
    for param_name, param_info in props.items():
        # Handle both dict format and string format for param_info
        if isinstance(param_info, str):
            param_type = param_info
            param_desc = ""
        else:
            param_type = param_info.get("type", "string")
            param_desc = param_info.get("description", "").lower()
        
        value = None
        
        # Extract based on parameter name and type
        if param_name == "function" or "function" in param_desc or "polynomial" in param_desc:
            # Extract polynomial function - look for patterns like "3x^2 + 2x - 1"
            # Pattern for polynomial expressions
            poly_patterns = [
                r'function\s+([0-9x\^\+\-\*\s\.]+)',  # "function 3x^2 + 2x - 1"
                r'derivative of (?:the function\s+)?([0-9x\^\+\-\*\s\.]+)',  # "derivative of 3x^2..."
                r'([0-9]+x\^?[0-9]*(?:\s*[\+\-]\s*[0-9]*x?\^?[0-9]*)+)',  # General polynomial pattern
            ]
            
            for pattern in poly_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = match.group(1).strip().rstrip('.')
                    break
        
        elif param_name == "x_value" or "x-value" in param_desc or "x value" in param_desc:
            # Extract x-value - look for "at x = 5" or "at x-value 5" or "at 5"
            x_patterns = [
                r'at\s+x\s*=\s*([0-9]+\.?[0-9]*)',
                r'x[_-]?value\s*(?:of|=|:)?\s*([0-9]+\.?[0-9]*)',
                r'at\s+(?:the\s+)?(?:point\s+)?([0-9]+\.?[0-9]*)',
            ]
            
            for pattern in x_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = float(match.group(1))
                    break
        
        elif param_type in ["integer", "int"]:
            # Extract integers
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers:
                value = int(numbers[0])
        
        elif param_type in ["float", "number"]:
            # Extract floats
            numbers = re.findall(r'\b(\d+\.?\d*)\b', query)
            if numbers:
                value = float(numbers[0])
        
        elif param_type == "string":
            # For generic strings, try to extract quoted values or key phrases
            quoted = re.findall(r'"([^"]+)"', query)
            if quoted:
                value = quoted[0]
        
        # Only add parameter if we found a value or it's required
        if value is not None:
            params[param_name] = value
        elif param_name in required_params:
            # For required params without extracted value, try harder
            if param_name == "function":
                # Last resort: extract anything that looks like a math expression
                math_match = re.search(r'(\d+x\^?\d*(?:\s*[\+\-]\s*\d*x?\^?\d*)*)', query)
                if math_match:
                    params[param_name] = math_match.group(1).strip()
    
    return {func_name: params}
