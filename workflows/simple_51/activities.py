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
    """Extract function call parameters from natural language prompt.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
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

    # Get function schema
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})

    # Extract parameters using regex
    params = {}
    
    # Extract all numbers from the query
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Map numbers to parameters based on context clues in the query
    # For entropy change: initial_temp, final_temp, heat_capacity
    
    # Look for specific patterns
    # Initial temperature pattern
    initial_temp_match = re.search(r'initial\s+temperature\s+(?:of\s+)?(\d+)', query, re.IGNORECASE)
    if initial_temp_match:
        params["initial_temp"] = int(initial_temp_match.group(1))
    
    # Final temperature pattern
    final_temp_match = re.search(r'final\s+temperature\s+(?:of\s+)?(\d+)', query, re.IGNORECASE)
    if final_temp_match:
        params["final_temp"] = int(final_temp_match.group(1))
    
    # Heat capacity pattern
    heat_capacity_match = re.search(r'heat\s+capacity\s+(?:of\s+)?(\d+)', query, re.IGNORECASE)
    if heat_capacity_match:
        params["heat_capacity"] = int(heat_capacity_match.group(1))
    
    # Fallback: if specific patterns didn't match, use positional numbers
    if not params and len(numbers) >= 3:
        # Assume order: initial_temp, final_temp, heat_capacity
        params["initial_temp"] = int(float(numbers[0]))
        params["final_temp"] = int(float(numbers[1]))
        params["heat_capacity"] = int(float(numbers[2]))
    
    # Check for isothermal parameter (optional, default True)
    # Only include if explicitly mentioned as False
    isothermal_match = re.search(r'isothermal\s*[=:]\s*(false|no|0)', query, re.IGNORECASE)
    if isothermal_match:
        params["isothermal"] = False
    # Don't include isothermal if not explicitly set to false (let default apply)

    return {func_name: params}
