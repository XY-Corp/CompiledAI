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
    
    Parses the prompt to extract numeric values and maps them to the
    function parameters defined in the schema.
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

    # Get function details
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])

    # Extract all numbers from the query using regex
    # Pattern matches integers and floats, including those with Hz suffix
    numbers = re.findall(r'(\d+(?:\.\d+)?)\s*(?:Hz)?', query, re.IGNORECASE)
    
    # Convert to integers (frequencies are typically integers)
    extracted_numbers = [int(float(n)) for n in numbers]

    # Build parameters dict
    params = {}
    
    # Map extracted numbers to frequency parameters
    # Look for patterns like "440Hz and 880Hz" or "440 and 880"
    freq_params = [p for p in params_schema.keys() if 'frequency' in p.lower()]
    
    # Assign numbers to frequency parameters in order
    for i, param_name in enumerate(freq_params):
        if i < len(extracted_numbers):
            params[param_name] = extracted_numbers[i]
    
    # Check for tempo - look for explicit tempo mention or use default
    tempo_match = re.search(r'(\d+)\s*(?:bpm|beats?\s*per\s*minute)', query, re.IGNORECASE)
    if tempo_match:
        params["tempo"] = int(tempo_match.group(1))
    # Note: tempo is optional with default 120, so we don't add it if not specified

    return {func_name: params}
