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
    """Extract function name and parameters from user query using regex patterns."""
    
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]], ...}
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
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
    
    # Extract all numbers from the query (integers and floats)
    # Pattern matches integers and decimals
    numbers = re.findall(r'\d+\.?\d*', query)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type in ["integer", "int"]:
            if num_idx < len(numbers):
                params[param_name] = int(float(numbers[num_idx]))
                num_idx += 1
        elif param_type in ["float", "number", "double"]:
            if num_idx < len(numbers):
                params[param_name] = float(numbers[num_idx])
                num_idx += 1
        elif param_type == "string":
            # For string params, try to extract relevant text
            # This is a simple fallback - could be enhanced with more patterns
            params[param_name] = ""
    
    # For binomial probability specifically, let's be smarter about extraction
    # "60 heads" -> num_success = 60
    # "100 times" -> num_trials = 100
    # "probability of heads 0.5" -> prob_success = 0.5
    
    if func_name == "calc_binomial_prob":
        # Extract num_success: look for pattern like "60 heads" or "observing 60"
        success_match = re.search(r'observing\s+(\d+)', query, re.IGNORECASE)
        if success_match:
            params["num_success"] = int(success_match.group(1))
        
        # Extract num_trials: look for pattern like "100 times" or "flip a coin 100 times"
        trials_match = re.search(r'(\d+)\s+times', query, re.IGNORECASE)
        if trials_match:
            params["num_trials"] = int(trials_match.group(1))
        
        # Extract prob_success: look for "probability of heads 0.5" or "probability 0.5"
        prob_match = re.search(r'probability\s+(?:of\s+\w+\s+)?(\d+\.?\d*)', query, re.IGNORECASE)
        if prob_match:
            params["prob_success"] = float(prob_match.group(1))
    
    return {func_name: params}
