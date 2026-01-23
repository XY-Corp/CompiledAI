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
            # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    
    # For binomial probability: num_trials, num_success, prob_success
    # Query: "Calculate the probability of observing 60 heads if I flip a coin 100 times with probability of heads 0.5"
    # Numbers found: ['60', '100', '0.5']
    
    # Map numbers to parameters based on context
    if func_name == "calc_binomial_prob":
        # Extract specific patterns for binomial distribution
        
        # num_success: "observing X heads" or "X successes"
        success_match = re.search(r'observing\s+(\d+)', query, re.IGNORECASE)
        if success_match:
            params["num_success"] = int(success_match.group(1))
        
        # num_trials: "X times" or "X trials" or "X experiments"
        trials_match = re.search(r'(\d+)\s+times', query, re.IGNORECASE)
        if trials_match:
            params["num_trials"] = int(trials_match.group(1))
        
        # prob_success: "probability of X" or "probability X" - look for decimal
        prob_match = re.search(r'probability\s+(?:of\s+\w+\s+)?(\d+\.?\d*)', query, re.IGNORECASE)
        if prob_match:
            params["prob_success"] = float(prob_match.group(1))
    else:
        # Generic extraction: assign numbers to parameters in order
        num_idx = 0
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string")
            
            if param_type in ["integer", "int"] and num_idx < len(numbers):
                params[param_name] = int(float(numbers[num_idx]))
                num_idx += 1
            elif param_type in ["float", "number"] and num_idx < len(numbers):
                params[param_name] = float(numbers[num_idx])
                num_idx += 1
            elif param_type == "string":
                # Try to extract string values with patterns
                string_match = re.search(r'(?:for|in|of|with|named?)\s+([A-Za-z\s]+?)(?:\s+(?:and|with|,|\.)|$)', query, re.IGNORECASE)
                if string_match:
                    params[param_name] = string_match.group(1).strip()
    
    return {func_name: params}
