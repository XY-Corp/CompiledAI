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
    
    Parses the user query to extract parameter values for the specified function,
    returning the function name as key with parameters as nested object.
    """
    # Parse prompt - handle BFCL format (may be JSON with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
            # Extract user query from nested BFCL structure
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

    # Parse functions list
    if isinstance(functions, str):
        try:
            functions = json.loads(functions)
        except json.JSONDecodeError:
            functions = []

    if not functions:
        return {"error": "No functions provided"}

    func = functions[0]
    func_name = func.get("name", "")
    params_schema = func.get("parameters", {}).get("properties", {})
    required_params = func.get("parameters", {}).get("required", [])

    # Extract numeric values from query using regex
    # Pattern for numbers with optional units (e.g., 100µF, 50mH, 2.5)
    number_pattern = r'(\d+(?:\.\d+)?)\s*([µuμ]?[FfHh]|[mM][FfHh]|[kK]?[Ωω])?'
    matches = re.findall(number_pattern, query)
    
    # Also extract plain numbers
    plain_numbers = re.findall(r'\d+(?:\.\d+)?', query)

    params = {}

    # For LC circuit: look for capacitance and inductance with units
    query_lower = query.lower()
    
    # Extract capacitance (look for µF, uF, F patterns)
    capacitance_match = re.search(r'capacitance\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*([µuμ]?[Ff])', query, re.IGNORECASE)
    if not capacitance_match:
        capacitance_match = re.search(r'(\d+(?:\.\d+)?)\s*([µuμ][Ff])', query)
    
    if capacitance_match:
        value = float(capacitance_match.group(1))
        unit = capacitance_match.group(2).lower() if capacitance_match.group(2) else ''
        # Convert to Farads
        if 'µ' in unit or 'u' in unit or 'μ' in unit:
            value = value * 1e-6  # microfarads to farads
        elif 'm' in unit:
            value = value * 1e-3  # millifarads to farads
        params["capacitance"] = value

    # Extract inductance (look for mH, H patterns)
    inductance_match = re.search(r'inductance\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*([mM]?[Hh])', query, re.IGNORECASE)
    if not inductance_match:
        inductance_match = re.search(r'(\d+(?:\.\d+)?)\s*([mM][Hh])', query)
    
    if inductance_match:
        value = float(inductance_match.group(1))
        unit = inductance_match.group(2).lower() if inductance_match.group(2) else ''
        # Convert to Henries
        if 'm' in unit:
            value = value * 1e-3  # millihenries to henries
        params["inductance"] = value

    # Check for round_off parameter (optional)
    round_match = re.search(r'round(?:ing|ed|_off)?\s*(?:to\s+)?(\d+)\s*(?:decimal|places)?', query, re.IGNORECASE)
    if round_match:
        params["round_off"] = int(round_match.group(1))

    return {func_name: params}
