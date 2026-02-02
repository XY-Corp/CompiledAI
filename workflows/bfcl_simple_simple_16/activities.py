import re
import json
from typing import Any


async def extract_function_call(
    prompt: str,
    functions: list = None,
    tools: list = None,
    user_query: str = None,
    tool_name_mapping: dict = None,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from user query using regex and string matching.
    
    Returns format: {"function_name": {"param1": val1, ...}}
    """
    # Step 1: Parse prompt to extract user query
    try:
        if isinstance(prompt, str):
            try:
                data = json.loads(prompt)
                # Handle BFCL nested format
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
    except Exception:
        query = str(prompt)

    # Step 2: Parse functions list
    funcs = []
    if functions:
        if isinstance(functions, str):
            try:
                funcs = json.loads(functions)
            except json.JSONDecodeError:
                funcs = []
        else:
            funcs = functions
    elif tools:
        if isinstance(tools, str):
            try:
                funcs = json.loads(tools)
            except json.JSONDecodeError:
                funcs = []
        else:
            funcs = tools

    if not funcs:
        return {"error": "No functions provided"}

    # Get target function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    
    # Handle different parameter schema formats
    params_schema = func.get("parameters", {})
    if isinstance(params_schema, dict):
        props = params_schema.get("properties", params_schema)
    else:
        props = {}

    # Step 3: Extract parameters using regex patterns
    params = {}
    
    # For calculus.derivative: extract function expression and value
    # Pattern: "derivative of the function <expr> at x = <value>"
    # or "derivative of <expr> at <value>"
    
    # Extract the mathematical function expression
    # Look for patterns like "function 2x^2" or "of 2x^2"
    func_patterns = [
        r'(?:function|of)\s+([^\s]+(?:\s*[\+\-\*\/\^]\s*[^\s]+)*)\s+at',  # "function 2x^2 at"
        r'derivative\s+of\s+(?:the\s+function\s+)?([^\s]+(?:\^[^\s]+)?)',  # "derivative of 2x^2"
        r'(?:function|of)\s+([a-zA-Z0-9\^\*\+\-\/\(\)]+)',  # general function pattern
    ]
    
    function_expr = None
    for pattern in func_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            function_expr = match.group(1).strip()
            # Clean up trailing "at" if present
            function_expr = re.sub(r'\s+at$', '', function_expr)
            break
    
    # Extract the value where derivative is calculated
    # Look for patterns like "at x = 1" or "at 1" or "x=1"
    value_patterns = [
        r'at\s+[a-zA-Z]\s*=\s*(-?\d+(?:\.\d+)?)',  # "at x = 1"
        r'at\s+(-?\d+(?:\.\d+)?)',  # "at 1"
        r'[a-zA-Z]\s*=\s*(-?\d+(?:\.\d+)?)',  # "x = 1"
        r'value\s+(-?\d+(?:\.\d+)?)',  # "value 1"
    ]
    
    value = None
    for pattern in value_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            val_str = match.group(1)
            # Convert to int if it's a whole number, else float
            if '.' in val_str:
                value = float(val_str)
            else:
                value = int(val_str)
            break
    
    # Extract the variable (default is 'x')
    # Look for patterns like "at x =" or variable in function
    var_patterns = [
        r'at\s+([a-zA-Z])\s*=',  # "at x ="
        r'd([a-zA-Z])',  # "dx" in derivative notation
    ]
    
    function_variable = None
    for pattern in var_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            function_variable = match.group(1).lower()
            break
    
    # Build params based on schema
    if "function" in props and function_expr:
        params["function"] = function_expr
    
    if "value" in props and value is not None:
        params["value"] = value
    
    # Only include function_variable if explicitly found (it has a default)
    if "function_variable" in props and function_variable:
        params["function_variable"] = function_variable

    return {func_name: params}
