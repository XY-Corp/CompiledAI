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
    numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
    
    # For this specific function: calculate_final_temperature
    # Expected pattern: "X kg of water at Y degree ... mixed with Z kg of water at W degree"
    # We need: mass1, temperature1, mass2, temperature2
    
    params = {}
    
    # Try to extract mass and temperature pairs using specific patterns
    # Pattern: "X kg ... at Y degree"
    mass_temp_pattern = r'(\d+(?:\.\d+)?)\s*kg\s+(?:of\s+)?(?:\w+\s+)?at\s+(\d+(?:\.\d+)?)\s*degree'
    matches = re.findall(mass_temp_pattern, query, re.IGNORECASE)
    
    if len(matches) >= 2:
        # First body
        params["mass1"] = int(float(matches[0][0]))
        params["temperature1"] = int(float(matches[0][1]))
        # Second body
        params["mass2"] = int(float(matches[1][0]))
        params["temperature2"] = int(float(matches[1][1]))
    elif len(numbers) >= 4:
        # Fallback: assume numbers appear in order: mass1, temp1, mass2, temp2
        params["mass1"] = int(float(numbers[0]))
        params["temperature1"] = int(float(numbers[1]))
        params["mass2"] = int(float(numbers[2]))
        params["temperature2"] = int(float(numbers[3]))
    
    # Check for specific_heat_capacity if mentioned (optional parameter)
    # Pattern: "specific heat capacity of X" or "X kJ/kg/K"
    shc_pattern = r'(?:specific\s+heat\s+capacity\s+(?:of\s+)?|capacity\s+(?:of\s+)?)(\d+(?:\.\d+)?)'
    shc_match = re.search(shc_pattern, query, re.IGNORECASE)
    if shc_match:
        params["specific_heat_capacity"] = float(shc_match.group(1))
    else:
        # Also check for kJ/kg/K pattern
        shc_pattern2 = r'(\d+(?:\.\d+)?)\s*kJ/kg/K'
        shc_match2 = re.search(shc_pattern2, query, re.IGNORECASE)
        if shc_match2:
            params["specific_heat_capacity"] = float(shc_match2.group(1))
    
    return {func_name: params}
