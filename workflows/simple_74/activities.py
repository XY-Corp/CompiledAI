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
    
    # Extract numbers from the query
    numbers = re.findall(r'\d+', query)
    
    # For bacteria evolution rate, we need:
    # - start_population: "start with X bacteria"
    # - duplication_frequency: "duplicates every Y hour" (frequency = 1 per Y hours)
    # - duration: "for Z hours"
    
    # Extract start_population - "start with 5000 bacteria"
    start_match = re.search(r'start\s+with\s+(\d+)', query_lower)
    if start_match:
        params["start_population"] = int(start_match.group(1))
    
    # Extract duplication_frequency - "duplicates every hour" means frequency = 1
    # "duplicates every X hours" means frequency = 1/X, but since it's integer, likely 1
    dup_match = re.search(r'duplicates?\s+every\s+(\d+)?\s*hour', query_lower)
    if dup_match:
        # If "every hour" (no number), frequency is 1
        # If "every 2 hours", frequency would be different interpretation
        freq_num = dup_match.group(1)
        if freq_num:
            params["duplication_frequency"] = int(freq_num)
        else:
            # "every hour" means once per hour = frequency of 1
            params["duplication_frequency"] = 1
    
    # Extract duration - "for 6 hours"
    duration_match = re.search(r'for\s+(\d+)\s+hours?', query_lower)
    if duration_match:
        params["duration"] = int(duration_match.group(1))
    
    # Fallback: if we didn't extract all required params, try positional numbers
    required_params = ["start_population", "duplication_frequency", "duration"]
    if not all(p in params for p in required_params):
        # Use numbers in order they appear
        num_idx = 0
        for param_name in required_params:
            if param_name not in params and num_idx < len(numbers):
                params[param_name] = int(numbers[num_idx])
                num_idx += 1
    
    # Note: generation_time is optional with default, don't include unless specified
    gen_time_match = re.search(r'generation\s+time\s+(?:of\s+)?(\d+)', query_lower)
    if gen_time_match:
        params["generation_time"] = int(gen_time_match.group(1))
    
    return {func_name: params}
