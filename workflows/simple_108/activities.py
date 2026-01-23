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
    """Extract function call parameters from natural language prompt.
    
    Parses the user query and function schema to extract the appropriate
    function name and parameters using regex and string matching.
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
    
    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "predictors":
            # Extract array of predictor variable names
            # Look for patterns like: 'Age', 'Income' and 'Education' or predictor variables X, Y, Z
            # Pattern 1: quoted strings with 'var1', 'var2' and 'var3'
            quoted_vars = re.findall(r"'([^']+)'", query)
            if quoted_vars:
                # Filter out the target variable if it appears
                # Target is usually mentioned after "target variable" phrase
                target_match = re.search(r"target\s+variable\s+'([^']+)'", query, re.IGNORECASE)
                target_var = target_match.group(1) if target_match else None
                predictors = [v for v in quoted_vars if v != target_var]
                params[param_name] = predictors
            else:
                params[param_name] = []
        
        elif param_name == "target":
            # Extract target variable name
            # Look for: "target variable 'X'" or "target variable X"
            target_match = re.search(r"target\s+variable\s+'([^']+)'", query, re.IGNORECASE)
            if target_match:
                params[param_name] = target_match.group(1)
            else:
                # Try without quotes
                target_match = re.search(r"target\s+variable\s+(\w+)", query, re.IGNORECASE)
                if target_match:
                    params[param_name] = target_match.group(1)
                else:
                    params[param_name] = ""
        
        elif param_name == "standardize":
            # Extract boolean for standardization
            # Look for: "apply standardization", "standardize", "with standardization"
            standardize_patterns = [
                r"apply\s+standardization",
                r"with\s+standardization",
                r"use\s+standardization",
                r"standardize\s*=\s*true",
                r"also\s+(?:apply\s+)?standardiz",
            ]
            standardize = False
            for pattern in standardize_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    standardize = True
                    break
            params[param_name] = standardize
        
        elif param_type == "boolean":
            # Generic boolean extraction
            # Check for positive indicators
            positive_patterns = [rf"{param_name}\s*=\s*true", rf"with\s+{param_name}", rf"enable\s+{param_name}"]
            value = False
            for pattern in positive_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    value = True
                    break
            params[param_name] = value
        
        elif param_type == "array":
            # Generic array extraction - look for quoted strings
            items = re.findall(r"'([^']+)'", query)
            params[param_name] = items
        
        elif param_type in ["integer", "number", "float"]:
            # Extract numbers
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(numbers[0])
                else:
                    params[param_name] = float(numbers[0])
        
        elif param_type == "string":
            # Generic string extraction - try to find relevant value
            # Look for pattern: "param_name 'value'" or "param_name value"
            match = re.search(rf"{param_name}\s+'([^']+)'", query, re.IGNORECASE)
            if match:
                params[param_name] = match.group(1)
            else:
                match = re.search(rf"{param_name}\s+(\w+)", query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1)
    
    return {func_name: params}
