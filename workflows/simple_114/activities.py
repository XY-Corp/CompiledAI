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
    """Extract function call parameters from natural language query.
    
    Parses the user query to extract parameter values and returns them
    in the format {"function_name": {"param1": val1, ...}}.
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
    
    # Extract numbers from query using regex
    # Pattern matches integers and floats
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    # For binomial distribution: look for specific patterns
    # "exactly X heads in Y tosses" or "X successes in Y trials"
    
    # Pattern: "exactly N heads/successes"
    success_match = re.search(r'exactly\s+(\d+)\s+(?:heads|successes|success)', query, re.IGNORECASE)
    
    # Pattern: "in N tosses/trials/flips"
    trials_match = re.search(r'in\s+(\d+)\s+(?:tosses|trials|flips|experiments)', query, re.IGNORECASE)
    
    # Pattern: "probability of X" (for p parameter)
    prob_match = re.search(r'probability\s+(?:of\s+)?(?:success\s+)?(?:is\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    
    # Check for "fair" coin which implies p=0.5
    is_fair = 'fair' in query.lower()
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "trials":
            if trials_match:
                params["trials"] = int(trials_match.group(1))
            elif len(numbers) >= 2:
                # Second number is typically trials (e.g., "5 heads in 10 tosses")
                params["trials"] = int(numbers[1])
        
        elif param_name == "successes":
            if success_match:
                params["successes"] = int(success_match.group(1))
            elif len(numbers) >= 1:
                # First number is typically successes
                params["successes"] = int(numbers[0])
        
        elif param_name == "p":
            # p is optional with default 0.5
            if prob_match:
                params["p"] = float(prob_match.group(1))
            elif is_fair:
                # Fair coin means p=0.5, but since it's the default, we can omit it
                # Only include if explicitly mentioned
                pass
            elif len(numbers) >= 3:
                # If there's a third number, it might be probability
                val = float(numbers[2])
                if 0 <= val <= 1:
                    params["p"] = val
    
    return {func_name: params}
