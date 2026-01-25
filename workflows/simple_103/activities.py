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
    """Extract function call parameters from natural language query about calculating area under a curve."""
    
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
    except (json.JSONDecodeError, TypeError):
        query = str(prompt)
    
    # Parse functions (may be JSON string)
    try:
        if isinstance(functions, str):
            funcs = json.loads(functions)
        else:
            funcs = functions
    except (json.JSONDecodeError, TypeError):
        funcs = []
    
    func = funcs[0] if funcs else {}
    func_name = func.get("name", "mathematics.calculate_area_under_curve")
    
    # Extract polynomial coefficients from expressions like "y=3x^2 + 2x - 4" or "3x^2 + 2x - 4"
    # Pattern: coefficient followed by x^power or x or constant
    polynomial = []
    
    # Find the polynomial expression (after y= or just the expression)
    poly_match = re.search(r'(?:y\s*=\s*)?([^,]+?)(?:,|\s+between|\s+from|\s+over|\s+in\s+the\s+interval|$)', query, re.IGNORECASE)
    if poly_match:
        poly_expr = poly_match.group(1).strip()
        
        # Parse polynomial terms - handle formats like "3x^2 + 2x - 4"
        # First, normalize the expression: replace - with + - for splitting
        normalized = poly_expr.replace('-', '+-').replace(' ', '')
        terms = [t for t in normalized.split('+') if t]
        
        # Determine the highest power to build coefficient array
        term_dict = {}  # power -> coefficient
        
        for term in terms:
            term = term.strip()
            if not term:
                continue
                
            # Match patterns: "3x^2", "-2x^3", "x^2", "5x", "x", "-4", "4"
            # Pattern for x^n terms
            power_match = re.match(r'^([+-]?\d*\.?\d*)x\^(\d+)$', term)
            if power_match:
                coef_str = power_match.group(1)
                if coef_str in ['', '+']:
                    coef = 1.0
                elif coef_str == '-':
                    coef = -1.0
                else:
                    coef = float(coef_str)
                power = int(power_match.group(2))
                term_dict[power] = coef
                continue
            
            # Pattern for x terms (power = 1)
            x_match = re.match(r'^([+-]?\d*\.?\d*)x$', term)
            if x_match:
                coef_str = x_match.group(1)
                if coef_str in ['', '+']:
                    coef = 1.0
                elif coef_str == '-':
                    coef = -1.0
                else:
                    coef = float(coef_str)
                term_dict[1] = coef
                continue
            
            # Pattern for constant terms
            const_match = re.match(r'^([+-]?\d+\.?\d*)$', term)
            if const_match:
                coef = float(const_match.group(1))
                term_dict[0] = coef
                continue
        
        # Build polynomial array in decreasing order of exponent
        if term_dict:
            max_power = max(term_dict.keys())
            polynomial = [term_dict.get(p, 0.0) for p in range(max_power, -1, -1)]
    
    # Extract limits from expressions like "between x = -1 and x = 2" or "from -1 to 2"
    limits = []
    
    # Pattern: "between x = -1 and x = 2" or "between -1 and 2"
    between_match = re.search(r'between\s+(?:x\s*=\s*)?([+-]?\d+\.?\d*)\s+and\s+(?:x\s*=\s*)?([+-]?\d+\.?\d*)', query, re.IGNORECASE)
    if between_match:
        limits = [float(between_match.group(1)), float(between_match.group(2))]
    else:
        # Pattern: "from x = -1 to x = 2" or "from -1 to 2"
        from_to_match = re.search(r'from\s+(?:x\s*=\s*)?([+-]?\d+\.?\d*)\s+to\s+(?:x\s*=\s*)?([+-]?\d+\.?\d*)', query, re.IGNORECASE)
        if from_to_match:
            limits = [float(from_to_match.group(1)), float(from_to_match.group(2))]
        else:
            # Pattern: "interval [a, b]" or "[a, b]"
            interval_match = re.search(r'\[([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)\]', query)
            if interval_match:
                limits = [float(interval_match.group(1)), float(interval_match.group(2))]
    
    return {
        func_name: {
            "polynomial": polynomial,
            "limits": limits
        }
    }
