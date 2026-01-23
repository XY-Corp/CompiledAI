from typing import Any, Dict, List, Optional
import re
import json

async def extract_quadratic_coefficients(
    equation_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract coefficients a, b, and c from the quadratic equation prompt using pattern matching."""
    
    def parse_coefficient(coeff_str: str, default: int = 0) -> int:
        """Parse coefficient string, handling implicit 1/-1 and empty strings."""
        if not coeff_str or coeff_str.strip() in ['', '+', '-']:
            return default
        
        coeff_str = coeff_str.replace(' ', '')
        
        if coeff_str == '+':
            return 1 if default != 0 else 0
        if coeff_str == '-':
            return -1 if default != 0 else 0
        
        try:
            return int(coeff_str)
        except ValueError:
            return default
    
    # Pattern 1: Direct coefficient extraction from text like "a=2, b=6, c=5"
    a_match = re.search(r'a\s*=\s*([+-]?\d+)', equation_text, re.IGNORECASE)
    b_match = re.search(r'b\s*=\s*([+-]?\d+)', equation_text, re.IGNORECASE)
    c_match = re.search(r'c\s*=\s*([+-]?\d+)', equation_text, re.IGNORECASE)
    
    if a_match and b_match and c_match:
        return {
            "a": int(a_match.group(1)),
            "b": int(b_match.group(1)),
            "c": int(c_match.group(1))
        }
    
    # Pattern 2: Standard form ax² + bx + c = 0 or ax^2 + bx + c = 0
    pattern_standard = r'([+-]?\s*\d*)\s*x\s*[\^²²]\s*2?\s*([+-]\s*\d*)\s*x\s*([+-]\s*\d+)'
    match_standard = re.search(pattern_standard, equation_text, re.IGNORECASE)
    
    if match_standard:
        a_str = match_standard.group(1).replace(' ', '')
        b_str = match_standard.group(2).replace(' ', '')
        c_str = match_standard.group(3).replace(' ', '')
        
        # Handle implicit coefficients
        a = parse_coefficient(a_str, default=1)
        b = parse_coefficient(b_str, default=0)
        c = parse_coefficient(c_str, default=0)
        
        return {"a": a, "b": b, "c": c}
    
    # Pattern 3: Extract coefficient patterns scattered in text
    x2_pattern = r'([+-]?\s*\d*)\s*x\s*[\^²²]\s*2?'
    x_pattern = r'([+-]?\s*\d+)\s*x(?!\s*[\^²²])'
    const_pattern = r'([+-]?\s*\d+)(?!\s*x)'
    
    x2_matches = re.findall(x2_pattern, equation_text, re.IGNORECASE)
    x_matches = re.findall(x_pattern, equation_text, re.IGNORECASE)
    const_matches = re.findall(const_pattern, equation_text, re.IGNORECASE)
    
    if x2_matches:
        a = parse_coefficient(x2_matches[0], default=1)
        b = parse_coefficient(x_matches[0] if x_matches else "", default=0)
        c = parse_coefficient(const_matches[-1] if const_matches else "", default=0)
        return {"a": a, "b": b, "c": c}
    
    # Default fallback - return zero coefficients
    return {"a": 0, "b": 0, "c": 0}


async def generate_function_call(
    coefficients: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> list[dict[str, Any]]:
    """Generate the properly formatted function call structure with extracted coefficients."""
    
    # Handle JSON string input defensively
    if isinstance(coefficients, str):
        coefficients = json.loads(coefficients)
    
    # Validate coefficients dict
    if not isinstance(coefficients, dict):
        return [{"error": f"coefficients must be dict, got {type(coefficients).__name__}"}]
    
    # Extract coefficients with defaults
    a = coefficients.get('a', 0)
    b = coefficients.get('b', 0) 
    c = coefficients.get('c', 0)
    
    # Generate function call in the exact format required
    # Each coefficient value must be wrapped in an array
    function_call = {
        "solve_quadratic_equation": {
            "a": [a],
            "b": [b],
            "c": [c]
        }
    }
    
    return [function_call]