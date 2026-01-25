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
    """Extract function name and parameters from user query and function schema.
    
    Returns a dict with function name as key and parameters as nested object.
    """
    # Parse prompt - may be JSON string with nested structure
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
        if "question" in data and isinstance(data["question"], list):
            if len(data["question"]) > 0 and isinstance(data["question"][0], list):
                if len(data["question"][0]) > 0 and isinstance(data["question"][0][0], dict):
                    query = data["question"][0][0].get("content", str(prompt))
                else:
                    query = str(prompt)
            else:
                query = str(prompt)
        else:
            query = str(prompt)
    except (json.JSONDecodeError, TypeError):
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
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        # For compound/formula parameters - extract molecular formula
        if param_name == "compound" or "formula" in param_desc or "compound" in param_desc:
            # Match molecular formulas like C6H12O6, H2O, NaCl, etc.
            formula_match = re.search(r'\b([A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*)\b', query)
            # Look for formula in parentheses like (C6H12O6)
            paren_match = re.search(r'\(([A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)+)\)', query)
            
            if paren_match:
                params[param_name] = paren_match.group(1)
            elif formula_match:
                # Filter out common words that might match pattern
                candidate = formula_match.group(1)
                # Look for more complex formulas with numbers
                complex_match = re.search(r'\b([A-Z][a-z]?\d+(?:[A-Z][a-z]?\d*)*)\b', query)
                if complex_match:
                    params[param_name] = complex_match.group(1)
                else:
                    params[param_name] = candidate
        
        # For unit parameters - extract unit from query
        elif param_name == "to_unit" or "unit" in param_desc:
            # Common unit patterns
            unit_patterns = [
                r'in\s+(grams?(?:/mole)?|g(?:/mol)?|kg(?:/mol)?|kilograms?(?:/mole)?)',
                r'(grams?(?:/mole)?|g(?:/mol)?|kg(?:/mol)?|kilograms?(?:/mole)?)',
                r'to\s+(grams?(?:/mole)?|g(?:/mol)?|kg(?:/mol)?)',
            ]
            
            unit_found = None
            for pattern in unit_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    unit_found = match.group(1)
                    break
            
            if unit_found:
                # Normalize unit
                unit_lower = unit_found.lower()
                if "gram" in unit_lower or unit_lower.startswith("g"):
                    if "/mol" in unit_lower or "/mole" in unit_lower:
                        params[param_name] = "grams/mole"
                    else:
                        params[param_name] = "grams/mole"  # Default for molecular weight
                elif "kg" in unit_lower or "kilogram" in unit_lower:
                    params[param_name] = "kg/mol"
                else:
                    params[param_name] = unit_found
            else:
                # Default unit for molecular weight
                params[param_name] = "grams/mole"
        
        # For string parameters - try to extract relevant text
        elif param_type == "string":
            # Generic string extraction - look for quoted strings or key phrases
            quoted = re.search(r'"([^"]+)"', query)
            if quoted:
                params[param_name] = quoted.group(1)
        
        # For numeric parameters
        elif param_type in ["integer", "number", "float"]:
            numbers = re.findall(r'\d+(?:\.\d+)?', query)
            if numbers:
                if param_type == "integer":
                    params[param_name] = int(float(numbers[0]))
                else:
                    params[param_name] = float(numbers[0])
    
    return {func_name: params}
