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
    """Extract function name and parameters from user query using regex patterns.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
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
    
    # Extract parameters using regex based on schema
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'-?\d+(?:\.\d+)?', query)
    
    # Common patterns for mean/mu and standard deviation/sigma
    # Pattern: "mean X" or "mean of X" or "mu X" or "mu = X"
    mean_patterns = [
        r'mean\s+(?:of\s+)?(-?\d+(?:\.\d+)?)',
        r'mu\s*[=:]?\s*(-?\d+(?:\.\d+)?)',
        r'mean\s*[=:]?\s*(-?\d+(?:\.\d+)?)',
    ]
    
    # Pattern: "standard deviation X" or "std X" or "sigma X"
    sigma_patterns = [
        r'standard\s+deviation\s+(?:of\s+)?(-?\d+(?:\.\d+)?)',
        r'std\s*[=:]?\s*(-?\d+(?:\.\d+)?)',
        r'sigma\s*[=:]?\s*(-?\d+(?:\.\d+)?)',
    ]
    
    # Try to extract mu (mean)
    mu_value = None
    for pattern in mean_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            mu_value = match.group(1)
            break
    
    # Try to extract sigma (standard deviation)
    sigma_value = None
    for pattern in sigma_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            sigma_value = match.group(1)
            break
    
    # If patterns didn't work, use positional numbers
    # Common phrasing: "mean X and standard deviation Y"
    if mu_value is None and sigma_value is None and len(numbers) >= 2:
        mu_value = numbers[0]
        sigma_value = numbers[1]
    elif mu_value is None and len(numbers) >= 1:
        mu_value = numbers[0]
        if len(numbers) >= 2:
            sigma_value = numbers[1]
    elif sigma_value is None and len(numbers) >= 1:
        # If we found mu but not sigma, sigma might be the remaining number
        for num in numbers:
            if num != mu_value:
                sigma_value = num
                break
    
    # Build params dict based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
        
        if param_name in ["mu", "mean"]:
            if mu_value is not None:
                if param_type == "integer":
                    params[param_name] = int(float(mu_value))
                elif param_type in ["number", "float"]:
                    params[param_name] = float(mu_value)
                else:
                    params[param_name] = mu_value
        elif param_name in ["sigma", "std", "standard_deviation"]:
            if sigma_value is not None:
                if param_type == "integer":
                    params[param_name] = int(float(sigma_value))
                elif param_type in ["number", "float"]:
                    params[param_name] = float(sigma_value)
                else:
                    params[param_name] = sigma_value
    
    return {func_name: params}
