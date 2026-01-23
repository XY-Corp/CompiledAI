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
        
        # Extract terms: look for patterns like "3x^2", "+2x", "-4", etc.
        # First, normalize the expression (handle spaces around operators)
        poly_expr = re.sub(r'\s*([+-])\s*', r' \1', poly_expr)
        
        # Find all terms with their coefficients and powers
        terms = {}
        
        # Pattern for terms like "3x^2", "-2x^3", "+x^2", "x", "-x", "5", "-4"
        term_pattern = r'([+-]?\s*\d*\.?\d*)\s*x\s*\^\s*(\d+)|([+-]?\s*\d*\.?\d*)\s*x(?!\^)|([+-]?\s*\d+\.?\d*)'
        
        for match in re.finditer(term_pattern, poly_expr):
            if match.group(1) is not None and match.group(2) is not None:
                # Term with x^n
                coef_str = match.group(1).replace(' ', '')
                power = int(match.group(2))
                if coef_str in ['', '+']:
                    coef = 1.0
                elif coef_str == '-':
                    coef = -1.0
                else:
                    coef = float(coef_str)
                terms[power] = terms.get(power, 0) + coef
            elif match.group(3) is not None:
                # Term with just x (power = 1)
                coef_str = match.group(3).replace(' ', '')
                if coef_str in ['', '+']:
                    coef = 1.0
                elif coef_str == '-':
                    coef = -1.0
                else:
                    coef = float(coef_str)
                terms[1] = terms.get(1, 0) + coef
            elif match.group(4) is not None:
                # Constant term (power = 0)
                coef_str = match.group(4).replace(' ', '')
                if coef_str and coef_str not in ['+', '-']:
                    coef = float(coef_str)
                    terms[0] = terms.get(0, 0) + coef
        
        # Convert to polynomial array (descending order of powers)
        if terms:
            max_power = max(terms.keys())
            polynomial = [terms.get(p, 0.0) for p in range(max_power, -1, -1)]
    
    # Extract limits from expressions like "between x = -1 and x = 2" or "from -1 to 2"
    limits = []
    
    # Try various patterns for limits
    limit_patterns = [
        r'between\s+x\s*=\s*([+-]?\d+\.?\d*)\s+and\s+x\s*=\s*([+-]?\d+\.?\d*)',
        r'between\s+([+-]?\d+\.?\d*)\s+and\s+([+-]?\d+\.?\d*)',
        r'from\s+x\s*=\s*([+-]?\d+\.?\d*)\s+to\s+x\s*=\s*([+-]?\d+\.?\d*)',
        r'from\s+([+-]?\d+\.?\d*)\s+to\s+([+-]?\d+\.?\d*)',
        r'interval\s*\[?\s*([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)\s*\]?',
        r'x\s*=\s*([+-]?\d+\.?\d*)\s+(?:and|to)\s+x\s*=\s*([+-]?\d+\.?\d*)',
    ]
    
    for pattern in limit_patterns:
        limit_match = re.search(pattern, query, re.IGNORECASE)
        if limit_match:
            limits = [float(limit_match.group(1)), float(limit_match.group(2))]
            break
    
    # Build result with exact parameter names from schema
    result = {
        func_name: {
            "polynomial": polynomial,
            "limits": limits
        }
    }
    
    return result
