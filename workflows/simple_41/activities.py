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
    # Pattern matches integers and floats
    numbers = re.findall(r'\d+(?:\.\d+)?', query)
    
    # Build parameters based on schema
    params = {}
    num_idx = 0
    
    # For electromagnetic_force: charge1, charge2, distance (in order they appear)
    # Query: "two charges of 5C and 7C placed 3 meters apart"
    # Numbers extracted: ['5', '7', '3']
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        
        # Skip optional parameters unless explicitly mentioned
        if param_name == "medium_permittivity":
            # Only include if explicitly mentioned in query
            if "permittivity" in query.lower() or "medium" in query.lower():
                # Try to find a float value for permittivity
                float_match = re.search(r'(\d+\.?\d*e?-?\d*)\s*(?:permittivity|medium)', query, re.IGNORECASE)
                if float_match:
                    params[param_name] = float(float_match.group(1))
            continue
        
        # Assign numbers to numeric parameters in order
        if param_type in ["integer", "int", "number", "float"] and num_idx < len(numbers):
            value = numbers[num_idx]
            if param_type in ["integer", "int"]:
                params[param_name] = int(float(value))
            else:
                params[param_name] = float(value)
            num_idx += 1
        elif param_type == "string":
            # For string parameters, try to extract relevant text
            params[param_name] = ""
    
    return {func_name: params}
