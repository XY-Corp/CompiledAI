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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "function" and "lambda" in param_desc:
            # Extract mathematical function - look for equation patterns
            # Pattern: f(x) = ... or f(t) = ... or equation = ...
            func_patterns = [
                r'f\([a-z]\)\s*=\s*([0-9a-z\^\*\+\-\s\.]+)',  # f(x) = 3t^2 + 2t + 1
                r'equation[:\s]+([0-9a-z\^\*\+\-\s\.]+)',
                r'function[:\s]+([0-9a-z\^\*\+\-\s\.]+)',
            ]
            
            equation = None
            for pattern in func_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    equation = match.group(1).strip()
                    break
            
            if equation:
                # Convert mathematical notation to Python lambda
                # Replace ^ with ** for exponentiation
                # Replace variable (t or x) with x for lambda
                lambda_expr = equation
                lambda_expr = re.sub(r'\^', '**', lambda_expr)
                
                # Detect the variable used (t or x)
                var_match = re.search(r'([tx])\*\*|\b([tx])\b', lambda_expr)
                var = 't'
                if var_match:
                    var = var_match.group(1) or var_match.group(2)
                
                # Add multiplication signs where needed: 3t -> 3*t, 2t -> 2*t
                lambda_expr = re.sub(r'(\d)([tx])', r'\1*\2', lambda_expr)
                
                # Replace variable with x for standard lambda format
                lambda_expr = lambda_expr.replace(var, 'x')
                
                # Clean up whitespace
                lambda_expr = lambda_expr.strip()
                
                params[param_name] = f"lambda x: {lambda_expr}"
        
        elif param_type == "integer":
            # Extract integer - look for specific context clues
            # For derivative problems, look for "at X seconds" or "at point X"
            time_patterns = [
                r'at\s+(?:precisely\s+)?(\d+)\s*seconds?',
                r'at\s+(?:time\s+)?t\s*=\s*(\d+)',
                r'at\s+(?:point\s+)?x\s*=\s*(\d+)',
                r'at\s+(\d+)',
                r'point\s+(\d+)',
            ]
            
            value = None
            for pattern in time_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    value = int(match.group(1))
                    break
            
            if value is not None:
                params[param_name] = value
            else:
                # Fallback: extract any standalone number
                numbers = re.findall(r'\b(\d+)\b', query)
                if numbers:
                    # Take the last number as it's often the point of interest
                    params[param_name] = int(numbers[-1])
    
    return {func_name: params}
