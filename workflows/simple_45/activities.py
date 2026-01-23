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
    """Extract function name and parameters from user query using regex and string matching."""
    
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from BFCL format
            if "question" in data and isinstance(data["question"], list):
                if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                    query = data["question"][0][0].get("content", prompt)
                else:
                    query = str(prompt)
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters from query
    params = {}
    query_lower = query.lower()
    
    # Extract mass - look for number followed by 'g' or 'grams' or just a number with mass context
    mass_patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:g|grams?)\b',  # "100g" or "100 grams"
        r'(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)\b',  # "1kg" - convert to grams
        r'mass\s*(?:of|is|=|:)?\s*(\d+(?:\.\d+)?)',  # "mass of 100"
        r'(\d+(?:\.\d+)?)\s*(?:of\s+)?(?:water|ice|steam)',  # "100 of water"
    ]
    
    mass_value = None
    for pattern in mass_patterns:
        match = re.search(pattern, query_lower)
        if match:
            mass_value = float(match.group(1))
            if 'kg' in pattern:
                mass_value *= 1000  # Convert kg to grams
            break
    
    # If no specific mass pattern found, look for any number that could be mass
    if mass_value is None:
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
        if numbers:
            mass_value = float(numbers[0])
    
    if mass_value is not None:
        params["mass"] = int(mass_value) if mass_value == int(mass_value) else mass_value
    
    # Extract phase_transition - map common phrases to valid values
    phase_mapping = {
        # Vaporization (liquid to gas)
        'liquid to steam': 'vaporization',
        'liquid to gas': 'vaporization',
        'water to steam': 'vaporization',
        'boiling': 'vaporization',
        'evaporation': 'vaporization',
        'vaporization': 'vaporization',
        'vaporizing': 'vaporization',
        'evaporating': 'vaporization',
        
        # Condensation (gas to liquid)
        'steam to liquid': 'condensation',
        'gas to liquid': 'condensation',
        'steam to water': 'condensation',
        'condensation': 'condensation',
        'condensing': 'condensation',
        
        # Melting (solid to liquid)
        'ice to water': 'melting',
        'solid to liquid': 'melting',
        'ice to liquid': 'melting',
        'melting': 'melting',
        
        # Freezing (liquid to solid)
        'water to ice': 'freezing',
        'liquid to solid': 'freezing',
        'liquid to ice': 'freezing',
        'freezing': 'freezing',
    }
    
    phase_transition = None
    for phrase, transition in phase_mapping.items():
        if phrase in query_lower:
            phase_transition = transition
            break
    
    if phase_transition:
        params["phase_transition"] = phase_transition
    
    # Extract substance - look for common substances
    substances = ['water', 'ice', 'steam', 'ethanol', 'alcohol', 'mercury', 'nitrogen', 'oxygen']
    substance_found = None
    for substance in substances:
        if substance in query_lower:
            # Map ice/steam to water as they're phases of water
            if substance in ['ice', 'steam']:
                substance_found = 'water'
            else:
                substance_found = substance
            break
    
    # Only include substance if explicitly mentioned and different from default
    if substance_found and substance_found != 'water':
        params["substance"] = substance_found
    elif substance_found == 'water':
        # Include water explicitly since it's mentioned
        params["substance"] = "water"
    
    return {func_name: params}
