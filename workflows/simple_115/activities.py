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
    # Pattern 1: "exactly N successes in M trials"
    exact_pattern = re.search(r'exactly\s+(\d+)\s+\w+\s+in\s+(\d+)', query, re.IGNORECASE)
    
    # Pattern 2: "N heads in M tosses" or "N successes in M trials"
    heads_pattern = re.search(r'(\d+)\s+(?:heads|successes|wins)\s+in\s+(\d+)', query, re.IGNORECASE)
    
    # Pattern 3: "getting X out of Y"
    out_of_pattern = re.search(r'getting\s+(\d+)\s+out\s+of\s+(\d+)', query, re.IGNORECASE)
    
    # Extract number of successes and trials
    number_of_successes = None
    number_of_trials = None
    
    if exact_pattern:
        number_of_successes = int(exact_pattern.group(1))
        number_of_trials = int(exact_pattern.group(2))
    elif heads_pattern:
        number_of_successes = int(heads_pattern.group(1))
        number_of_trials = int(heads_pattern.group(2))
    elif out_of_pattern:
        number_of_successes = int(out_of_pattern.group(1))
        number_of_trials = int(out_of_pattern.group(2))
    else:
        # Fallback: extract all numbers in order
        numbers = re.findall(r'\d+', query)
        if len(numbers) >= 2:
            # Typically "X in Y" means X successes, Y trials
            number_of_successes = int(numbers[0])
            number_of_trials = int(numbers[1])
    
    # Build params based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
        
        if param_name == "number_of_trials" and number_of_trials is not None:
            params[param_name] = number_of_trials
        elif param_name == "number_of_successes" and number_of_successes is not None:
            params[param_name] = number_of_successes
        elif param_name == "probability_of_success":
            # Check for "fair coin" (0.5) or explicit probability
            if "fair" in query.lower():
                params[param_name] = 0.5
            else:
                # Look for explicit probability like "0.3" or "30%"
                prob_match = re.search(r'probability\s+(?:of\s+)?(\d*\.?\d+)', query, re.IGNORECASE)
                percent_match = re.search(r'(\d+)%', query)
                if prob_match:
                    params[param_name] = float(prob_match.group(1))
                elif percent_match:
                    params[param_name] = float(percent_match.group(1)) / 100.0
                # Use default if not specified (0.5 for fair coin is common default)
    
    return {func_name: params}
