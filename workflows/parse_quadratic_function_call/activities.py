from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class QuadraticFunction(BaseModel):
    """Define the expected structure for quadratic function call."""
    a: int
    b: int  
    c: int
    root_type: str

async def extract_quadratic_parameters(
    prompt_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user input text to extract quadratic equation coefficients and generate function call parameters.
    
    Args:
        prompt_text: The complete user input text containing quadratic equation coefficients and solving requirements
        available_functions: List of available function definitions to understand parameter requirements and constraints
        
    Returns:
        Dict with solve_quadratic function call parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Ensure prompt_text is not None and is a string
        if prompt_text is None:
            return {"solve_quadratic": {"a": 1, "b": 0, "c": 0, "root_type": "real"}}
        
        if not isinstance(prompt_text, str):
            prompt_text = str(prompt_text)
            
        # Extract quadratic coefficients from the prompt text using regex
        # Look for patterns like "3x^2 - 11x - 4" or "ax^2 + bx + c"
        
        # Initialize coefficients
        a, b, c = 1, 0, 0
        root_type = "real"  # default
        
        # Clean the text for easier parsing
        text = prompt_text.lower().replace(" ", "")
        
        # Look for root_type specification
        if "all" in text or "complex" in text or "imaginary" in text:
            root_type = "all"
        
        # Pattern matching for quadratic coefficients
        # Handle various formats like "3x^2-11x-4", "x^2+2x+1", etc.
        
        # Extract coefficient of x^2 (a coefficient)
        a_match = re.search(r'([+-]?\d*)\s*x\s*\^?\s*2', text)
        if a_match:
            a_coeff = a_match.group(1)
            if a_coeff == '' or a_coeff == '+':
                a = 1
            elif a_coeff == '-':
                a = -1
            else:
                a = int(a_coeff)
        
        # Extract coefficient of x (b coefficient)
        # Look for x terms that are not x^2
        b_match = re.search(r'([+-]?\d*)\s*x(?!\s*\^?\s*2)', text)
        if b_match:
            b_coeff = b_match.group(1)
            if b_coeff == '' or b_coeff == '+':
                b = 1
            elif b_coeff == '-':
                b = -1
            else:
                b = int(b_coeff)
        
        # Extract constant term (c coefficient)
        # Look for standalone numbers (not coefficients of x terms)
        # Remove x terms first to find constants
        no_x_terms = re.sub(r'[+-]?\d*\s*x\s*(\^\s*2)?', '', text)
        c_match = re.search(r'([+-]?\d+)', no_x_terms)
        if c_match:
            c = int(c_match.group(1))
        
        # Alternative parsing: look for explicit "a=3, b=-11, c=-4" format
        a_explicit = re.search(r'a\s*=\s*([+-]?\d+)', text)
        b_explicit = re.search(r'b\s*=\s*([+-]?\d+)', text)
        c_explicit = re.search(r'c\s*=\s*([+-]?\d+)', text)
        
        if a_explicit:
            a = int(a_explicit.group(1))
        if b_explicit:
            b = int(b_explicit.group(1))
        if c_explicit:
            c = int(c_explicit.group(1))
        
        # Validate the parsed coefficients using Pydantic
        validated_params = QuadraticFunction(a=a, b=b, c=c, root_type=root_type)
        
        return {
            "solve_quadratic": validated_params.model_dump()
        }
        
    except Exception as e:
        # Return default values if parsing fails
        return {
            "solve_quadratic": {
                "a": 1,
                "b": 0, 
                "c": 0,
                "root_type": "real"
            }
        }