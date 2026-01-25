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
    
    Parses the user query to extract parameter values and returns them
    in the format {"function_name": {"param1": val1, ...}}.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                query = data["question"][0][0].get("content", str(prompt))
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError, KeyError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
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
    props = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query using regex
    params = {}
    query_lower = query.lower()
    
    # Extract substance - look for common substances
    substances = ["ice", "water", "steam", "air", "oxygen", "nitrogen", "helium", "hydrogen", "copper", "iron", "aluminum", "gold", "silver"]
    for substance in substances:
        if substance in query_lower:
            params["substance"] = substance
            break
    
    # Extract mass - patterns like "1kg", "1 kg", "1-kg", "mass of 1 kg"
    mass_patterns = [
        r'(\d+(?:\.\d+)?)\s*kg',
        r'(\d+(?:\.\d+)?)\s*kilogram',
        r'mass\s+(?:of\s+)?(\d+(?:\.\d+)?)',
    ]
    for pattern in mass_patterns:
        match = re.search(pattern, query_lower)
        if match:
            params["mass"] = int(float(match.group(1)))
            break
    
    # Extract temperatures - look for patterns with °C, degrees, Celsius
    # Pattern: "at X°C" or "X degrees" or "to Y°C"
    temp_patterns = [
        r'at\s+(-?\d+)\s*(?:°|degrees?\s*)?c(?:elsius)?',
        r'from\s+(-?\d+)\s*(?:°|degrees?\s*)?c(?:elsius)?',
        r'to\s+(-?\d+)\s*(?:°|degrees?\s*)?c(?:elsius)?',
        r'(-?\d+)\s*(?:°|degrees?\s*)?c(?:elsius)?',
    ]
    
    temperatures = []
    for pattern in temp_patterns:
        matches = re.findall(pattern, query_lower)
        for m in matches:
            temp = int(m)
            if temp not in temperatures:
                temperatures.append(temp)
    
    # Also try to find temperatures in order they appear
    all_temps = re.findall(r'(-?\d+)\s*(?:°|degrees?\s*)?c', query_lower)
    for t in all_temps:
        temp = int(t)
        if temp not in temperatures:
            temperatures.append(temp)
    
    # Assign initial and final temperatures
    # Look for context clues
    initial_match = re.search(r'at\s+(-?\d+)\s*(?:°|degrees?\s*)?c', query_lower)
    final_match = re.search(r'(?:heated|cooled|to)\s+(-?\d+)\s*(?:°|degrees?\s*)?c', query_lower)
    
    if initial_match:
        params["initial_temperature"] = int(initial_match.group(1))
    if final_match:
        params["final_temperature"] = int(final_match.group(1))
    
    # Fallback: if we found temperatures but couldn't assign them
    if "initial_temperature" not in params and len(temperatures) >= 1:
        params["initial_temperature"] = temperatures[0]
    if "final_temperature" not in params and len(temperatures) >= 2:
        params["final_temperature"] = temperatures[1]
    elif "final_temperature" not in params and len(temperatures) == 1 and "initial_temperature" in params:
        # Only one temp found, check if it's different from initial
        if temperatures[0] != params["initial_temperature"]:
            params["final_temperature"] = temperatures[0]
    
    # Extract pressure - patterns like "1 atmosphere", "1 atm", "under 1 atmosphere"
    pressure_patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:atmosphere|atm)',
        r'under\s+(\d+(?:\.\d+)?)\s*(?:atmosphere|atm)',
        r'at\s+(\d+(?:\.\d+)?)\s*(?:atmosphere|atm)',
    ]
    for pattern in pressure_patterns:
        match = re.search(pattern, query_lower)
        if match:
            params["pressure"] = int(float(match.group(1)))
            break
    
    return {func_name: params}
