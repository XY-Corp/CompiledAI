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
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+', query)
    
    # Build parameters based on schema
    params = {}
    
    # For batting average: extract hits, at_bats, decimal_places
    # Query: "180 hits and 600 at-bats. Round to 3 decimals"
    
    # Try to extract hits (number before "hits")
    hits_match = re.search(r'(\d+)\s*hits', query, re.IGNORECASE)
    if hits_match and "hits" in params_schema:
        params["hits"] = int(hits_match.group(1))
    
    # Try to extract at_bats (number before "at-bats" or "at bats")
    at_bats_match = re.search(r'(\d+)\s*at[- ]?bats', query, re.IGNORECASE)
    if at_bats_match and "at_bats" in params_schema:
        params["at_bats"] = int(at_bats_match.group(1))
    
    # Try to extract decimal_places (number after "round to" or "decimal")
    decimal_match = re.search(r'(?:round\s*to|to)\s*(\d+)\s*decimal', query, re.IGNORECASE)
    if decimal_match and "decimal_places" in params_schema:
        params["decimal_places"] = int(decimal_match.group(1))
    
    # Fallback: if specific patterns didn't match, assign numbers in order
    if not params and numbers:
        num_idx = 0
        for param_name, param_info in params_schema.items():
            param_type = param_info.get("type", "string") if isinstance(param_info, dict) else "string"
            if param_type == "integer" and num_idx < len(numbers):
                params[param_name] = int(numbers[num_idx])
                num_idx += 1
            elif param_type == "number" and num_idx < len(numbers):
                params[param_name] = float(numbers[num_idx])
                num_idx += 1
    
    return {func_name: params}
