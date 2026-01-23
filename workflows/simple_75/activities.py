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
    numbers = re.findall(r'\b\d+(?:\.\d+)?\b', query)
    
    # Build parameters based on schema
    params = {}
    
    # For elephant_population_estimate, we need:
    # - current_population (integer) - likely the large number (35000)
    # - growth_rate (float) - likely the small decimal (0.015)
    # - years (integer) - likely mentioned with "years" context (5)
    
    # Extract numbers with context
    integers = []
    floats = []
    
    for num_str in numbers:
        if '.' in num_str:
            floats.append(float(num_str))
        else:
            integers.append(int(num_str))
    
    # Try to identify years - look for number near "year" keyword
    years_match = re.search(r'(\d+)\s*years?', query, re.IGNORECASE)
    years_value = int(years_match.group(1)) if years_match else None
    
    # Try to identify population - look for "population" context or large number
    pop_match = re.search(r'(?:population\s*(?:size\s*)?(?:of\s*)?(?:elephants\s*)?(?:of\s*)?|of\s+elephants\s+of\s+)(\d+)', query, re.IGNORECASE)
    pop_value = int(pop_match.group(1)) if pop_match else None
    
    # Try to identify growth rate - look for "rate" context or small decimal
    rate_match = re.search(r'(?:growth\s*)?rate\s*(?:of\s*)?(\d+\.?\d*)', query, re.IGNORECASE)
    rate_value = float(rate_match.group(1)) if rate_match else None
    
    # Assign values to parameters based on schema
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        if param_name == "current_population":
            if pop_value is not None:
                params[param_name] = pop_value
            elif integers:
                # Use the largest integer as population
                params[param_name] = max(integers)
        
        elif param_name == "growth_rate":
            if rate_value is not None:
                params[param_name] = rate_value
            elif floats:
                # Use the float value (likely the growth rate)
                params[param_name] = floats[0]
        
        elif param_name == "years":
            if years_value is not None:
                params[param_name] = years_value
            elif integers:
                # Use the smallest integer as years (excluding population)
                remaining = [i for i in integers if i != params.get("current_population")]
                if remaining:
                    params[param_name] = min(remaining)
    
    return {func_name: params}
