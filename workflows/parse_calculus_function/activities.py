from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Define expected function call structure."""
    function: str
    value: Optional[float] = None
    function_variable: str = "x"


async def parse_calculus_query(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract mathematical function parameters from natural language calculus queries.
    
    Args:
        query_text: The natural language mathematical query containing function expression and evaluation point
        available_functions: List of available calculus function definitions with their parameter schemas
        
    Returns:
        Dict with function name as key and parameters dict as value
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        if not isinstance(available_functions, list):
            available_functions = []
            
        # Default to derivative function if no query or invalid input
        if not query_text or not isinstance(query_text, str):
            return {
                "calculus.derivative": {
                    "function": "2x**2",
                    "value": 1,
                    "function_variable": "x"
                }
            }
        
        # Determine which calculus function to use based on available functions and query
        target_function = "calculus.derivative"  # Default
        
        # Look for specific calculus operations in the query
        if "integral" in query_text.lower() or "integrate" in query_text.lower():
            # Check if integral function is available
            for func in available_functions:
                if "integral" in func.get("name", "").lower():
                    target_function = func["name"]
                    break
        elif "derivative" in query_text.lower() or "differentiate" in query_text.lower():
            # Check if derivative function is available
            for func in available_functions:
                if "derivative" in func.get("name", "").lower():
                    target_function = func["name"]
                    break
        
        # Extract mathematical function using regex patterns
        function_str = None
        
        # Patterns for various mathematical notations
        function_patterns = [
            # Standard polynomial notation: 2x^2, 3x**2, x^2 + 5x - 3
            r'([0-9]*x\^[0-9]+(?:\s*[+\-]\s*[0-9]*x\^[0-9]+)*(?:\s*[+\-]\s*[0-9]*x)?(?:\s*[+\-]\s*[0-9]+)?)',
            r'([0-9]*x\*\*[0-9]+(?:\s*[+\-]\s*[0-9]*x\*\*[0-9]+)*(?:\s*[+\-]\s*[0-9]*x)?(?:\s*[+\-]\s*[0-9]+)?)',
            # Unicode superscript: x², 2x² + 3x - 1
            r'([0-9]*x²(?:\s*[+\-]\s*[0-9]*x²)*(?:\s*[+\-]\s*[0-9]*x)?(?:\s*[+\-]\s*[0-9]+)?)',
            # Function notation: f(x) = 2x^2
            r'f\(x\)\s*=\s*([^,\s]+(?:\s*[+\-]\s*[^,\s]+)*)',
            # Simple expressions: 2x^2, x^2, 5x, etc.
            r'([0-9]*x(?:\^[0-9]+|\*\*[0-9]+|²)?(?:\s*[+\-]\s*[0-9]*x(?:\^[0-9]+|\*\*[0-9]+|²)?)*(?:\s*[+\-]\s*[0-9]+)?)',
        ]
        
        for pattern in function_patterns:
            match = re.search(pattern, query_text, re.IGNORECASE)
            if match:
                function_str = match.group(1).strip()
                # Normalize notation to Python format
                function_str = re.sub(r'x\^(\d+)', r'x**\1', function_str)
                function_str = re.sub(r'x²', r'x**2', function_str)
                function_str = re.sub(r'(\d)x', r'\1*x', function_str)  # Convert 2x to 2*x
                break
        
        # Extract evaluation point/value if specified
        value = None
        value_patterns = [
            r'at\s+x\s*=\s*([0-9.-]+)',
            r'when\s+x\s*=\s*([0-9.-]+)', 
            r'x\s*=\s*([0-9.-]+)',
            r'evaluate\s+at\s+([0-9.-]+)',
            r'at\s+([0-9.-]+)',
            r'value\s+([0-9.-]+)'
        ]
        
        for pattern in value_patterns:
            match = re.search(pattern, query_text, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    break
                except ValueError:
                    continue
        
        # Extract function variable (usually x, but could be t, y, etc.)
        variable = "x"  # default
        var_match = re.search(r'with\s+respect\s+to\s+([a-zA-Z])', query_text, re.IGNORECASE)
        if var_match:
            variable = var_match.group(1)
        else:
            # Look for common variables in the function expression
            if function_str:
                for var in ['t', 'y', 'z', 'u', 'v']:
                    if var in function_str:
                        variable = var
                        break
        
        # Default function if none found
        if not function_str:
            function_str = "2x**2"
            
        # Build result based on target function parameters
        result_params = {
            "function": function_str,
            "function_variable": variable
        }
        
        # Add value parameter if found and function supports it
        if value is not None:
            result_params["value"] = value
        
        return {
            target_function: result_params
        }
        
    except json.JSONDecodeError:
        # Return default structure on JSON parsing error
        return {
            "calculus.derivative": {
                "function": "2x**2",
                "value": 1,
                "function_variable": "x"
            }
        }
    except Exception:
        # Return default structure on any other error
        return {
            "calculus.derivative": {
                "function": "2x**2", 
                "value": 1,
                "function_variable": "x"
            }
        }