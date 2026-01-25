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
    
    Parses the prompt to extract the user query, then uses regex to extract
    parameter values based on the function schema.
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
    
    # Extract all numbers from the query (integers and floats)
    numbers = re.findall(r'(\d+\.?\d*)', query)
    
    # Process each parameter based on its type
    num_idx = 0
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_type == "float":
            # Look for specific patterns first
            if param_name == "charge":
                # Pattern: "charge of X Coulombs" or "X Coulombs"
                charge_match = re.search(r'charge\s+of\s+(\d+\.?\d*)', query, re.IGNORECASE)
                if not charge_match:
                    charge_match = re.search(r'(\d+\.?\d*)\s*[Cc]oulombs?', query)
                if charge_match:
                    params[param_name] = float(charge_match.group(1))
                elif num_idx < len(numbers):
                    params[param_name] = float(numbers[num_idx])
                    num_idx += 1
            else:
                # Generic float extraction
                if num_idx < len(numbers):
                    params[param_name] = float(numbers[num_idx])
                    num_idx += 1
        
        elif param_type == "integer":
            # Look for specific patterns first
            if param_name == "distance":
                # Pattern: "X meters away" or "distance of X"
                dist_match = re.search(r'(\d+)\s*meters?\s*(?:away)?', query, re.IGNORECASE)
                if not dist_match:
                    dist_match = re.search(r'distance\s+(?:of\s+)?(\d+)', query, re.IGNORECASE)
                if dist_match:
                    params[param_name] = int(dist_match.group(1))
                elif num_idx < len(numbers):
                    params[param_name] = int(float(numbers[num_idx]))
                    num_idx += 1
            else:
                # Generic integer extraction
                if num_idx < len(numbers):
                    params[param_name] = int(float(numbers[num_idx]))
                    num_idx += 1
        
        elif param_type == "string":
            # For optional string params like "medium", only include if explicitly mentioned
            if param_name == "medium":
                # Look for medium specification in query
                medium_match = re.search(r'(?:in|through)\s+(?:a\s+)?(\w+)', query, re.IGNORECASE)
                if medium_match:
                    medium_val = medium_match.group(1).lower()
                    # Only set if it's a valid medium (not generic words)
                    if medium_val not in ['the', 'a', 'an', 'which', 'that']:
                        params[param_name] = medium_val
                # Don't include default - let the function handle it
    
    return {func_name: params}
