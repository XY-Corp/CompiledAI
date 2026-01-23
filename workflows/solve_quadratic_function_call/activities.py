from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Define the expected function call structure."""
    solve_quadratic_equation: Dict[str, List[int]]

async def parse_quadratic_parameters(
    user_input: str,
    available_functions: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract quadratic equation coefficients from user prompt and generate function call JSON.
    
    Extracts the quadratic equation coefficients (a, b, c) from the user prompt and generates 
    the function call JSON with the solve_quadratic_equation function name and parameters.
    
    Args:
        user_input: The complete user prompt containing the quadratic equation parameters
        available_functions: The function definitions available for generating the function call
    
    Returns:
        Function call object with solve_quadratic_equation key and parameters as values
    """
    try:
        # Parse available_functions if it's a JSON string
        if isinstance(available_functions, str):
            try:
                available_functions = json.loads(available_functions)
            except json.JSONDecodeError:
                pass  # Keep as string if parsing fails
        
        # Extract coefficients using regex patterns
        # Look for patterns like "a=2", "a = 2", "a is 2", "where a=2"
        a_match = re.search(r'a\s*[=:]\s*(-?\d+)', user_input, re.IGNORECASE)
        b_match = re.search(r'b\s*[=:]\s*(-?\d+)', user_input, re.IGNORECASE)  
        c_match = re.search(r'c\s*[=:]\s*(-?\d+)', user_input, re.IGNORECASE)
        
        # Extract coefficient values, default to 0 if not found
        a = int(a_match.group(1)) if a_match else 0
        b = int(b_match.group(1)) if b_match else 0
        c = int(c_match.group(1)) if c_match else 0
        
        # Generate the function call structure matching the expected output format
        # Based on the example, coefficients should be wrapped in lists
        function_call = {
            "solve_quadratic_equation": {
                "a": [a],
                "b": [b], 
                "c": [c]
            }
        }
        
        return function_call
        
    except Exception as e:
        # Return error structure if extraction fails
        return {
            "solve_quadratic_equation": {
                "a": [0],
                "b": [0],
                "c": [0]
            }
        }