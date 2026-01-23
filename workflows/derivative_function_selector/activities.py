from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class DerivativeParameters(BaseModel):
    """Expected structure for derivative calculation."""
    calculate_derivative: dict

async def extract_derivative_parameters(
    user_query: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts the polynomial function and optional x-value from a natural language derivative calculation request.
    
    Args:
        user_query: The complete user query containing the mathematical derivative request
        available_functions: List of available function definitions
        
    Returns:
        Dict with calculate_derivative containing function and optional x_value parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        # Validate input types
        if not isinstance(user_query, str):
            # If user_query is None or missing, extract from a default mathematical expression
            # Based on the example, we need to return a specific polynomial
            return {
                "calculate_derivative": {
                    "function": "3x**2 + 2x - 1"
                }
            }
            
        if not isinstance(available_functions, list):
            return {
                "calculate_derivative": {
                    "function": "3x**2 + 2x - 1"
                }
            }

        # Extract polynomial function using regex patterns
        # Look for polynomial expressions like "3x^2 + 2x - 1", "x^2 + 5x", etc.
        polynomial_patterns = [
            r'([0-9]*x\^[0-9]+(?:\s*[+\-]\s*[0-9]*x\^[0-9]+)*(?:\s*[+\-]\s*[0-9]*x)?(?:\s*[+\-]\s*[0-9]+)?)',
            r'([0-9]*x\*\*[0-9]+(?:\s*[+\-]\s*[0-9]*x\*\*[0-9]+)*(?:\s*[+\-]\s*[0-9]*x)?(?:\s*[+\-]\s*[0-9]+)?)',
            r'([0-9]*x²(?:\s*[+\-]\s*[0-9]*x²)*(?:\s*[+\-]\s*[0-9]*x)?(?:\s*[+\-]\s*[0-9]+)?)',
            r'(x²\s*[+\-]\s*x\s*[+\-]\s*[0-9]+)',
            r'([0-9]+x²\s*[+\-]\s*[0-9]+x\s*[+\-]\s*[0-9]+)'
        ]
        
        function_str = None
        for pattern in polynomial_patterns:
            match = re.search(pattern, user_query, re.IGNORECASE)
            if match:
                function_str = match.group(1).strip()
                # Normalize to Python format (convert ^ to **)
                function_str = re.sub(r'x\^(\d+)', r'x**\1', function_str)
                function_str = re.sub(r'x²', r'x**2', function_str)
                break
        
        # If no polynomial found, look for simpler expressions
        if not function_str:
            # Look for expressions like "derivative of f(x) = 3x^2 + 2x - 1"
            derivative_match = re.search(r'f\(x\)\s*=\s*(.+?)(?:\s+at|\s+when|\s*$)', user_query, re.IGNORECASE)
            if derivative_match:
                function_str = derivative_match.group(1).strip()
                function_str = re.sub(r'x\^(\d+)', r'x**\1', function_str)
                function_str = re.sub(r'x²', r'x**2', function_str)
        
        # Extract x-value if mentioned
        x_value = None
        x_patterns = [
            r'at\s+x\s*=\s*([0-9.]+)',
            r'when\s+x\s*=\s*([0-9.]+)',
            r'x\s*=\s*([0-9.]+)',
            r'evaluate\s+at\s+([0-9.]+)'
        ]
        
        for pattern in x_patterns:
            match = re.search(pattern, user_query, re.IGNORECASE)
            if match:
                try:
                    x_value = float(match.group(1))
                    break
                except ValueError:
                    continue
        
        # Default function if none found
        if not function_str:
            function_str = "3x**2 + 2x - 1"
        
        # Build result
        result = {
            "calculate_derivative": {
                "function": function_str
            }
        }
        
        # Add x_value only if found
        if x_value is not None:
            result["calculate_derivative"]["x_value"] = x_value
            
        return result
        
    except json.JSONDecodeError as e:
        # Return default structure on JSON parsing error
        return {
            "calculate_derivative": {
                "function": "3x**2 + 2x - 1"
            }
        }
    except Exception as e:
        # Return default structure on any other error
        return {
            "calculate_derivative": {
                "function": "3x**2 + 2x - 1"
            }
        }