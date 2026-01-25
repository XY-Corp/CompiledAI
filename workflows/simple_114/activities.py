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
    
    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # For binomial distribution: look for patterns like "X heads in Y tosses" or "exactly X ... in Y"
    # Pattern: "exactly N successes in M trials"
    exact_pattern = re.search(r'exactly\s+(\d+)\s+\w+\s+in\s+(\d+)', query, re.IGNORECASE)
    # Pattern: "N heads in M tosses/flips"
    heads_pattern = re.search(r'(\d+)\s+(?:heads?|successes?|wins?)\s+in\s+(\d+)', query, re.IGNORECASE)
    # Pattern: "in N ... tosses/trials"
    trials_pattern = re.search(r'in\s+(\d+)\s+(?:\w+\s+)?(?:tosses?|trials?|flips?|experiments?)', query, re.IGNORECASE)
    
    successes = None
    trials = None
    
    if exact_pattern:
        successes = int(exact_pattern.group(1))
        trials = int(exact_pattern.group(2))
    elif heads_pattern:
        successes = int(heads_pattern.group(1))
        trials = int(heads_pattern.group(2))
    elif trials_pattern and len(numbers) >= 2:
        # Try to extract from general number patterns
        trials = int(trials_pattern.group(1))
        # Find the other number for successes
        for num in numbers:
            if int(num) != trials:
                successes = int(num)
                break
    elif len(numbers) >= 2:
        # Fallback: assume first number is successes, second is trials
        # Common pattern: "5 heads in 10 tosses" -> 5 successes, 10 trials
        successes = int(numbers[0])
        trials = int(numbers[1])
    
    # Assign to parameter names from schema
    if "trials" in params_schema and trials is not None:
        params["trials"] = trials
    if "successes" in params_schema and successes is not None:
        params["successes"] = successes
    
    # Check for probability parameter - for fair coin, p=0.5
    if "p" in params_schema:
        # Look for explicit probability mention
        prob_pattern = re.search(r'probability\s+(?:of\s+)?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        p_pattern = re.search(r'p\s*=\s*(\d+(?:\.\d+)?)', query, re.IGNORECASE)
        
        if prob_pattern:
            params["p"] = float(prob_pattern.group(1))
        elif p_pattern:
            params["p"] = float(p_pattern.group(1))
        elif "fair" in query.lower():
            # Fair coin implies p=0.5, but it's the default so we can omit it
            # Only include if explicitly needed
            pass
    
    return {func_name: params}
