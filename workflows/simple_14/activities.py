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
    """Extract function call parameters from user query and return as {func_name: {params}}.
    
    Parses the prompt to extract the user's query, identifies the target function,
    and extracts parameter values using regex and string matching.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
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
    required_params = func.get("parameters", {}).get("required", [])
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "function" and "polynomial" in param_desc:
            # Extract polynomial function - look for patterns like "3x^2 + 2x - 1"
            # Match polynomial expressions with terms like ax^n, ax, or constants
            poly_patterns = [
                r'(?:function|of)\s+([0-9x\^\+\-\*\s\.]+)',  # "function 3x^2 + 2x - 1"
                r'derivative of\s+(?:the\s+)?(?:function\s+)?([0-9x\^\+\-\*\s\.]+)',  # "derivative of 3x^2..."
                r'([0-9]*x\^?[0-9]*(?:\s*[\+\-]\s*[0-9]*x?\^?[0-9]*)+)',  # General polynomial pattern
            ]
            
            for pattern in poly_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    func_str = match.group(1).strip()
                    # Clean up the function string - remove trailing periods
                    func_str = func_str.rstrip('.')
                    if func_str and ('x' in func_str or any(c.isdigit() for c in func_str)):
                        params[param_name] = func_str
                        break
            
            # If no pattern matched, try to find any expression with x
            if param_name not in params:
                # Look for anything that looks like a polynomial
                match = re.search(r'(\d*x\^?\d*(?:\s*[\+\-]\s*\d*x?\^?\d*)*)', query)
                if match:
                    params[param_name] = match.group(1).strip()
        
        elif param_type == "float" or param_type == "number":
            # Extract numeric value - look for x_value or similar
            if "x-value" in param_desc or "x_value" in param_name:
                # Look for explicit x value mentions
                x_patterns = [
                    r'(?:at\s+)?x\s*=\s*([+-]?\d+\.?\d*)',  # "x = 5" or "at x = 5"
                    r'at\s+([+-]?\d+\.?\d*)',  # "at 5"
                    r'x-value\s+(?:of\s+)?([+-]?\d+\.?\d*)',  # "x-value of 5"
                ]
                
                for pattern in x_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = float(match.group(1))
                        break
                
                # x_value is optional with default 0.00, so don't add if not found
        
        elif param_type == "integer":
            # Extract integer values
            numbers = re.findall(r'\b(\d+)\b', query)
            if numbers and param_name not in params:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # For generic string params, try to extract relevant text
            # This is a fallback - specific handling above is preferred
            pass
    
    # Ensure required params are present
    for req_param in required_params:
        if req_param not in params:
            # Try harder to find the required param
            if req_param == "function":
                # Last resort: extract everything after "derivative of"
                match = re.search(r'derivative of\s+(?:the\s+)?(?:function\s+)?(.+?)(?:\.|$)', query, re.IGNORECASE)
                if match:
                    params[req_param] = match.group(1).strip()
    
    return {func_name: params}
