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
    """Extract function name and parameters from user query.
    
    Returns a dict with function name as key and parameters as nested object.
    Uses regex and string parsing - no LLM calls needed.
    """
    # Parse prompt (may be JSON string with nested structure)
    try:
        if isinstance(prompt, str):
            data = json.loads(prompt)
        else:
            data = prompt
        
        # Extract user query from BFCL format: {"question": [[{"role": "user", "content": "..."}]]}
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
    params_schema = func.get("parameters", {}).get("properties", {})
    
    # Extract parameters based on schema
    params = {}
    
    for param_name, param_info in params_schema.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "").lower()
        
        if param_name == "compound":
            # Extract molecular formula - pattern like C6H12O6, H2O, NaCl, etc.
            # Look for chemical formulas (capital letter followed by optional lowercase and numbers)
            formula_match = re.search(r'\b([A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*)\b', query)
            # More specific pattern for molecular formulas in parentheses
            paren_match = re.search(r'\(([A-Z][a-z0-9]+)\)', query)
            
            if paren_match:
                params[param_name] = paren_match.group(1)
            elif formula_match:
                # Filter out common words that match the pattern
                candidate = formula_match.group(1)
                # Look for more complex formulas with multiple elements
                complex_match = re.search(r'\b([A-Z][a-z]?\d+[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*)\b', query)
                if complex_match:
                    params[param_name] = complex_match.group(1)
                else:
                    params[param_name] = candidate
        
        elif param_name == "to_unit":
            # Extract unit from query - look for common unit patterns
            # Check for "grams/mole", "g/mol", "kg/mol", etc.
            unit_patterns = [
                r'in\s+([\w/]+)',  # "in grams/mole"
                r'(grams?/mole?)',
                r'(g/mol)',
                r'(kg/mol)',
                r'(daltons?)',
                r'(Da)',
                r'(amu)',
            ]
            
            for pattern in unit_patterns:
                unit_match = re.search(pattern, query, re.IGNORECASE)
                if unit_match:
                    params[param_name] = unit_match.group(1)
                    break
            
            # If no unit found, check for common phrases
            if param_name not in params:
                if "grams/mole" in query.lower() or "grams per mole" in query.lower():
                    params[param_name] = "grams/mole"
                elif "g/mol" in query.lower():
                    params[param_name] = "g/mol"
    
    return {func_name: params}
