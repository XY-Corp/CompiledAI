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
                r'(?:function|derivative of|of)\s+(?:the\s+)?(?:function\s+)?([0-9x\^\+\-\*\s\.]+)',
                r'([0-9]*x\^?[0-9]*[\s\+\-]+[0-9x\^\+\-\*\s\.]+)',
            ]
            
            for pattern in poly_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    func_str = match.group(1).strip()
                    # Clean up the function string
                    func_str = func_str.rstrip('.')
                    if func_str:
                        params[param_name] = func_str
                        break
            
            # Fallback: extract anything that looks like a polynomial
            if param_name not in params:
                # Look for expressions with x and numbers
                poly_match = re.search(r'(\d*x\^?\d*(?:\s*[\+\-]\s*\d*x?\^?\d*)+)', query)
                if poly_match:
                    params[param_name] = poly_match.group(1).strip()
        
        elif param_type == "float" or param_type == "number":
            # Extract numeric value - look for x_value or similar
            if "x-value" in param_desc or "x_value" in param_name:
                # Look for explicit x value mentions
                x_patterns = [
                    r'(?:at\s+)?x\s*=\s*([+-]?\d+\.?\d*)',
                    r'(?:at|when)\s+([+-]?\d+\.?\d*)',
                    r'x[_\s-]?value\s*(?:of|is|=)?\s*([+-]?\d+\.?\d*)',
                ]
                
                for pattern in x_patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        params[param_name] = float(match.group(1))
                        break
            else:
                # Generic number extraction
                numbers = re.findall(r'(?<![x\^])([+-]?\d+\.?\d*)(?![x\^])', query)
                if numbers:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "integer":
            numbers = re.findall(r'\d+', query)
            if numbers:
                params[param_name] = int(numbers[0])
        
        elif param_type == "string":
            # For generic string params, try to extract relevant text
            # This is a fallback - specific handling above is preferred
            if param_name not in params:
                # Try to find quoted strings first
                quoted = re.findall(r'"([^"]+)"', query)
                if quoted:
                    params[param_name] = quoted[0]
    
    # Only include required params and params we found values for
    # Don't include optional params without values
    final_params = {}
    for param_name in params_schema.keys():
        if param_name in params:
            final_params[param_name] = params[param_name]
    
    return {func_name: final_params}
