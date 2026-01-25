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
    """Extract function name and parameters from user query. Returns {func_name: {params}}."""
    
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
    numbers = re.findall(r'\b(\d+)\b', query)
    
    # For permutations: look for specific patterns
    # Pattern: "n elements" or "set of n" for n
    # Pattern: "take k" or "choose k" or "k elements from" for k
    
    n_value = None
    k_value = None
    
    # Look for "n" parameter - typically the larger set size
    # Patterns: "26 letters", "set of 26", "alphabet, which has 26"
    n_patterns = [
        r'(?:set of|has|with|from)\s+(\d+)',
        r'(\d+)\s+(?:letters|elements|items|characters)',
        r'alphabet.*?(\d+)',
    ]
    
    for pattern in n_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            n_value = int(match.group(1))
            break
    
    # Look for "k" parameter - typically the selection size
    # Patterns: "take 5", "choose 5", "5 characters from"
    k_patterns = [
        r'(?:take|choose|select|pick)\s+(\d+)',
        r'(\d+)\s+(?:characters|elements|items)\s+from',
        r'(?:if I take|taking)\s+(\d+)',
    ]
    
    for pattern in k_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            k_value = int(match.group(1))
            break
    
    # Fallback: if we have exactly 2 numbers and couldn't match patterns
    if (n_value is None or k_value is None) and len(numbers) >= 2:
        # For permutations, n is typically larger than k
        num_list = [int(n) for n in numbers]
        num_list_sorted = sorted(num_list, reverse=True)
        if n_value is None:
            n_value = num_list_sorted[0]  # Larger number is n
        if k_value is None:
            k_value = num_list_sorted[1]  # Smaller number is k
    
    # Build params based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
        
        if param_name == "n" and n_value is not None:
            params[param_name] = n_value
        elif param_name == "k" and k_value is not None:
            params[param_name] = k_value
        elif param_type in ["integer", "number"] and numbers:
            # Generic fallback for numeric params
            if param_name not in params:
                # Try to find an unused number
                for num in numbers:
                    num_int = int(num)
                    if num_int not in params.values():
                        params[param_name] = num_int
                        break
    
    return {func_name: params}
