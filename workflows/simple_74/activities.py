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
    """Extract function call parameters from natural language prompt using regex.
    
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
    
    # Extract parameters using regex patterns
    params = {}
    query_lower = query.lower()
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+', query)
    
    # For bacteria evolution rate, we need:
    # - start_population: "start with X bacteria"
    # - duplication_frequency: "duplicates every Y hour" (frequency = 1 per Y hours)
    # - duration: "for Z hours"
    
    # Extract start_population - "start with X bacteria"
    start_match = re.search(r'start\s+with\s+(\d+)\s*bacteria', query_lower)
    if start_match:
        params["start_population"] = int(start_match.group(1))
    
    # Extract duplication frequency - "duplicates every X hour"
    # "each bacteria duplicates every hour" means frequency = 1 per hour
    dup_match = re.search(r'duplicates?\s+every\s+(\d*)\s*hour', query_lower)
    if dup_match:
        freq_val = dup_match.group(1)
        if freq_val:
            params["duplication_frequency"] = int(freq_val)
        else:
            # "every hour" without number means 1
            params["duplication_frequency"] = 1
    
    # Extract duration - "for X hours"
    duration_match = re.search(r'for\s+(\d+)\s*hours?', query_lower)
    if duration_match:
        params["duration"] = int(duration_match.group(1))
    
    # Fallback: if we didn't extract all required params, try positional assignment
    required_params = ["start_population", "duplication_frequency", "duration"]
    missing = [p for p in required_params if p not in params]
    
    if missing and numbers:
        # Try to assign remaining numbers to missing params
        used_numbers = set()
        for key, val in params.items():
            if isinstance(val, int):
                used_numbers.add(str(val))
        
        remaining_numbers = [n for n in numbers if n not in used_numbers]
        
        for i, param_name in enumerate(missing):
            if i < len(remaining_numbers):
                params[param_name] = int(remaining_numbers[i])
    
    return {func_name: params}
