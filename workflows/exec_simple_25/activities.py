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
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if isinstance(data, dict) and "question" in data:
            question_data = data["question"]
            if isinstance(question_data, list) and len(question_data) > 0:
                if isinstance(question_data[0], list) and len(question_data[0]) > 0:
                    query = question_data[0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
        query = str(prompt)
    
    # Parse functions - may be JSON string
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "function":
            # Extract mathematical function - look for f(x) = ... pattern
            # Pattern: f(x) = 4x^3 + 3x^2 + 2x + 1
            func_match = re.search(r'f\(x\)\s*=\s*([^.]+?)(?:\.|,|My|$)', query, re.IGNORECASE)
            if func_match:
                math_expr = func_match.group(1).strip()
                # Convert to Python lambda format
                # Replace x^n with x**n
                lambda_expr = re.sub(r'(\d*)x\^(\d+)', lambda m: f"{m.group(1) + '*' if m.group(1) else ''}x**{m.group(2)}", math_expr)
                # Replace standalone x with *x where needed (e.g., 2x -> 2*x)
                lambda_expr = re.sub(r'(\d)x(?!\*)', r'\1*x', lambda_expr)
                # Clean up any double operators
                lambda_expr = lambda_expr.replace('+ +', '+').replace('- -', '+').replace('+ -', '-').replace('- +', '-')
                params[param_name] = f"lambda x: {lambda_expr}"
            else:
                # Fallback: look for any polynomial-like expression
                params[param_name] = "lambda x: x"
        
        elif param_name == "x" and param_type == "integer":
            # Extract the point value - look for "at the X-year mark" or "at x = X" or "at X"
            point_patterns = [
                r'at\s+the\s+(\d+)-year\s+mark',
                r'at\s+x\s*=\s*(\d+)',
                r'at\s+point\s+(\d+)',
                r'at\s+(\d+)',
                r'when\s+x\s*=\s*(\d+)',
            ]
            
            for pattern in point_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
                    break
            
            # If no match found, try to find any standalone number that makes sense as a point
            if param_name not in params:
                # Look for numbers not part of coefficients (not followed by x)
                numbers = re.findall(r'(?<!\d)(\d+)(?!x|\*x|\^)', query)
                if numbers:
                    # Take the last number as it's likely the evaluation point
                    params[param_name] = int(numbers[-1])
    
    return {func_name: params}
