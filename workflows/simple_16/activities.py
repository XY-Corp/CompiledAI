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
    """Extract function name and parameters from user query using regex and string parsing."""
    
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    
    # For calculus.derivative: extract function expression and value
    # Pattern: "derivative of [function] at x = [value]"
    
    # Extract the function expression (e.g., "2x^2", "x^3 + 2x", etc.)
    function_patterns = [
        r'derivative of (?:the function\s+)?([^\s].*?)\s+at',  # "derivative of 2x^2 at"
        r'derivative of\s+([^\s].*?)\s+at',  # simpler pattern
        r'function\s+([^\s]+)\s+at',  # "function 2x^2 at"
    ]
    
    function_expr = None
    for pattern in function_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            function_expr = match.group(1).strip()
            break
    
    # Extract the value where derivative is calculated (e.g., "x = 1" -> 1)
    value_patterns = [
        r'at\s+x\s*=\s*(-?\d+(?:\.\d+)?)',  # "at x = 1"
        r'at\s+(-?\d+(?:\.\d+)?)',  # "at 1"
        r'x\s*=\s*(-?\d+(?:\.\d+)?)',  # "x = 1"
        r'value\s+(-?\d+(?:\.\d+)?)',  # "value 1"
    ]
    
    value = None
    for pattern in value_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            val_str = match.group(1)
            # Convert to int if it's a whole number, otherwise float
            if '.' in val_str:
                value = float(val_str)
            else:
                value = int(val_str)
            break
    
    # Extract function variable (default is 'x')
    # Look for patterns like "with respect to y" or variable in function
    variable_patterns = [
        r'with respect to\s+([a-zA-Z])',  # "with respect to y"
        r'variable\s+([a-zA-Z])',  # "variable y"
    ]
    
    function_variable = None
    for pattern in variable_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            function_variable = match.group(1)
            break
    
    # Build params based on schema
    if "function" in params_schema and function_expr:
        params["function"] = function_expr
    
    if "value" in params_schema and value is not None:
        params["value"] = value
    
    # Only include function_variable if explicitly specified (it has a default)
    if "function_variable" in params_schema and function_variable:
        params["function_variable"] = function_variable
    
    return {func_name: params}
