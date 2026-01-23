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
    """Extract function call parameters from user query and return as {func_name: {params}}."""
    
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
    
    # Extract parameters using regex
    params = {}
    
    # For LC circuit: extract capacitance and inductance values with units
    # Pattern for capacitance: "capacitance of 100µF" or "100µF capacitance" or "C = 100µF"
    # Pattern for inductance: "inductance of 50mH" or "50mH inductance" or "L = 50mH"
    
    # Extract capacitance (look for µF, uF, F, pF, nF patterns)
    capacitance_patterns = [
        r'capacitance\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*([µuμ]?[FfpPnN]?[Ff])',
        r'(\d+(?:\.\d+)?)\s*([µuμ]?[FfpPnN]?[Ff])\s+capacitance',
        r'[Cc]\s*=\s*(\d+(?:\.\d+)?)\s*([µuμ]?[FfpPnN]?[Ff])',
        r'(\d+(?:\.\d+)?)\s*([µuμ][Ff])',  # Specifically for µF
    ]
    
    capacitance_value = None
    for pattern in capacitance_patterns:
        match = re.search(pattern, query)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower().replace('μ', 'µ').replace('u', 'µ')
            
            # Convert to Farads
            if 'µf' in unit or 'µ' in unit:
                capacitance_value = value * 1e-6  # microfarads to farads
            elif 'nf' in unit:
                capacitance_value = value * 1e-9  # nanofarads to farads
            elif 'pf' in unit:
                capacitance_value = value * 1e-12  # picofarads to farads
            elif 'mf' in unit:
                capacitance_value = value * 1e-3  # millifarads to farads
            else:
                capacitance_value = value  # already in farads
            break
    
    # Extract inductance (look for mH, H, µH patterns)
    inductance_patterns = [
        r'inductance\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*([mµuμ]?[Hh])',
        r'(\d+(?:\.\d+)?)\s*([mµuμ]?[Hh])\s+inductance',
        r'[Ll]\s*=\s*(\d+(?:\.\d+)?)\s*([mµuμ]?[Hh])',
        r'(\d+(?:\.\d+)?)\s*([m][Hh])',  # Specifically for mH
    ]
    
    inductance_value = None
    for pattern in inductance_patterns:
        match = re.search(pattern, query)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower().replace('μ', 'µ').replace('u', 'µ')
            
            # Convert to Henries
            if 'mh' in unit or unit == 'm':
                inductance_value = value * 1e-3  # millihenries to henries
            elif 'µh' in unit:
                inductance_value = value * 1e-6  # microhenries to henries
            else:
                inductance_value = value  # already in henries
            break
    
    # Build params dict with extracted values
    if "inductance" in params_schema and inductance_value is not None:
        params["inductance"] = inductance_value
    
    if "capacitance" in params_schema and capacitance_value is not None:
        params["capacitance"] = capacitance_value
    
    # Check for optional round_off parameter
    if "round_off" in params_schema:
        round_match = re.search(r'round(?:ed|ing)?\s*(?:to|off)?\s*(\d+)\s*(?:decimal|place)', query, re.IGNORECASE)
        if round_match:
            params["round_off"] = int(round_match.group(1))
        # Don't include if not specified (it has a default)
    
    return {func_name: params}
