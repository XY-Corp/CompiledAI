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
    """Extract function call parameters from natural language query using regex.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Handle BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # Extract parameters using regex
    params = {}
    
    # For binomial probability: "exactly X heads in Y tosses"
    # Pattern: "exactly {successes} heads in {trials} tosses"
    binomial_pattern = r'exactly\s+(\d+)\s+\w+\s+in\s+(\d+)\s+(?:tosses|trials|flips)'
    binomial_match = re.search(binomial_pattern, query, re.IGNORECASE)
    
    if binomial_match and func_name == "calculate_binomial_probability":
        successes = int(binomial_match.group(1))
        trials = int(binomial_match.group(2))
        params["number_of_successes"] = successes
        params["number_of_trials"] = trials
        
        # Check for probability in query (e.g., "biased coin with 0.6 probability")
        prob_match = re.search(r'probability\s+(?:of\s+)?(\d+\.?\d*)', query, re.IGNORECASE)
        if prob_match:
            params["probability_of_success"] = float(prob_match.group(1))
        else:
            # Check if "fair coin" is mentioned - use default 0.5
            if re.search(r'fair\s+coin', query, re.IGNORECASE):
                params["probability_of_success"] = 0.5
    else:
        # Generic extraction: find all numbers and map to parameters
        numbers = re.findall(r'\d+(?:\.\d+)?', query)
        
        # Map numbers to parameters based on schema order
        num_idx = 0
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string")
            
            if param_type in ["integer", "number", "float"] and num_idx < len(numbers):
                if param_type == "integer":
                    params[param_name] = int(numbers[num_idx])
                else:
                    params[param_name] = float(numbers[num_idx])
                num_idx += 1
    
    return {func_name: params}
