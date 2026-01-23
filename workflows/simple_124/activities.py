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
    # Pattern: "dataset_A with the values X, Y, Z" or similar
    
    # Extract dataset_A values
    dataset_a_match = re.search(
        r'dataset_A\s+(?:with\s+)?(?:the\s+)?(?:values?\s+)?(\d+(?:\s*,\s*\d+)*)',
        query,
        re.IGNORECASE
    )
    if dataset_a_match:
        values_str = dataset_a_match.group(1)
        dataset_a = [int(x.strip()) for x in values_str.split(',')]
        params["dataset_A"] = dataset_a
    
    # Extract dataset_B values
    dataset_b_match = re.search(
        r'dataset_B\s+(?:with\s+)?(?:the\s+)?(?:values?\s+)?(\d+(?:\s*,\s*\d+)*)',
        query,
        re.IGNORECASE
    )
    if dataset_b_match:
        values_str = dataset_b_match.group(1)
        dataset_b = [int(x.strip()) for x in values_str.split(',')]
        params["dataset_B"] = dataset_b
    
    # Check for alpha parameter (optional)
    alpha_match = re.search(r'alpha\s*(?:=|:|\s)\s*([\d.]+)', query, re.IGNORECASE)
    if alpha_match:
        params["alpha"] = float(alpha_match.group(1))
    
    # Alternative: significance level mentioned
    sig_match = re.search(r'significance\s+(?:level\s+)?(?:of\s+)?([\d.]+)', query, re.IGNORECASE)
    if sig_match and "alpha" not in params:
        params["alpha"] = float(sig_match.group(1))
    
    return {func_name: params}
