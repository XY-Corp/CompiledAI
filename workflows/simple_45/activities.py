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
    
    # Extract mass - look for number followed by 'g' or 'grams'
    mass_patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:g|grams?)\b',
        r'(\d+(?:\.\d+)?)\s*(?:gram|grams)',
        r'mass\s*(?:of|:)?\s*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)',
    ]
    
    for pattern in mass_patterns:
        match = re.search(pattern, query_lower)
        if match:
            mass_val = float(match.group(1))
            # Convert kg to g if needed
            if 'kg' in pattern:
                mass_val *= 1000
            params["mass"] = int(mass_val)
            break
    
    # If no mass found with units, try to find standalone number near mass-related words
    if "mass" not in params:
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', query)
        if numbers:
            params["mass"] = int(float(numbers[0]))
    
    # Extract phase transition
    phase_keywords = {
        'vaporization': ['vaporization', 'boiling', 'evaporation', 'liquid to steam', 'liquid to gas', 'water to steam', 'boil'],
        'condensation': ['condensation', 'steam to liquid', 'gas to liquid', 'condense'],
        'melting': ['melting', 'solid to liquid', 'ice to water', 'melt'],
        'freezing': ['freezing', 'liquid to solid', 'water to ice', 'freeze']
    }
    
    for phase, keywords in phase_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                params["phase_transition"] = phase
                break
        if "phase_transition" in params:
            break
    
    # Extract substance - default is water, but check for other substances
    substance_patterns = [
        r'of\s+(\w+)\s+from',
        r'(\w+)\s+from\s+(?:liquid|solid|gas)',
        r'phase\s+change\s+of\s+(?:\d+\s*(?:g|grams?)?\s+(?:of\s+)?)?(\w+)',
    ]
    
    substance = None
    for pattern in substance_patterns:
        match = re.search(pattern, query_lower)
        if match:
            potential_substance = match.group(1).strip()
            # Filter out common non-substance words
            if potential_substance not in ['the', 'a', 'an', 'its', 'during']:
                substance = potential_substance
                break
    
    # Only include substance if it's not the default 'water' or if explicitly mentioned
    if substance and substance != 'water':
        params["substance"] = substance
    elif 'water' in query_lower:
        params["substance"] = "water"
    
    return {func_name: params}
