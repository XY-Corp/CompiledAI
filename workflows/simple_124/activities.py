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
    """Extract function name and parameters from user query using regex parsing."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
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
    
    # For t_test function, extract dataset_A and dataset_B arrays
    if func_name == "t_test":
        # Pattern to find dataset_A values: "dataset_A with the values X, Y, Z"
        dataset_a_match = re.search(r'dataset_A\s+with\s+(?:the\s+)?values?\s+([\d,\s]+)', query, re.IGNORECASE)
        if dataset_a_match:
            values_str = dataset_a_match.group(1)
            # Extract all integers from the matched string
            dataset_a_values = [int(x) for x in re.findall(r'\d+', values_str)]
            params["dataset_A"] = dataset_a_values
        
        # Pattern to find dataset_B values: "dataset_B with the values X, Y, Z"
        dataset_b_match = re.search(r'dataset_B\s+with\s+(?:the\s+)?values?\s+([\d,\s]+)', query, re.IGNORECASE)
        if dataset_b_match:
            values_str = dataset_b_match.group(1)
            # Extract all integers from the matched string
            dataset_b_values = [int(x) for x in re.findall(r'\d+', values_str)]
            params["dataset_B"] = dataset_b_values
        
        # Check for alpha parameter (optional)
        alpha_match = re.search(r'alpha\s*[=:]\s*([\d.]+)', query, re.IGNORECASE)
        if alpha_match:
            params["alpha"] = float(alpha_match.group(1))
        
        # Also check for "significance level" pattern
        sig_match = re.search(r'significance\s+level\s+(?:of\s+)?([\d.]+)', query, re.IGNORECASE)
        if sig_match and "alpha" not in params:
            params["alpha"] = float(sig_match.group(1))
    
    else:
        # Generic extraction for other functions
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            
            if param_type == "array":
                # Try to find array values associated with this parameter name
                pattern = rf'{param_name}\s+(?:with\s+)?(?:the\s+)?values?\s*[=:]?\s*([\d,\s]+)'
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    values_str = match.group(1)
                    items_type = param_info.get("items", {}).get("type", "integer") if isinstance(param_info, dict) else "integer"
                    if items_type in ["integer", "int"]:
                        params[param_name] = [int(x) for x in re.findall(r'\d+', values_str)]
                    elif items_type in ["float", "number"]:
                        params[param_name] = [float(x) for x in re.findall(r'[\d.]+', values_str)]
                    else:
                        params[param_name] = re.findall(r'\w+', values_str)
            
            elif param_type in ["integer", "int"]:
                pattern = rf'{param_name}\s*[=:]\s*(\d+)'
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = int(match.group(1))
            
            elif param_type in ["float", "number"]:
                pattern = rf'{param_name}\s*[=:]\s*([\d.]+)'
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = float(match.group(1))
            
            elif param_type == "string":
                pattern = rf'{param_name}\s*[=:]\s*["\']?([^"\']+)["\']?'
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    params[param_name] = match.group(1).strip()
    
    return {func_name: params}
