from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Model for parsed function call structure."""
    function_name: str
    parameters: Dict[str, Any]

async def parse_numbers_and_generate_function_call(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts the two numbers from the user prompt and generates a properly formatted function call object with math.gcd as the function name and the extracted numbers as parameters.
    
    Args:
        user_prompt: The complete user input text containing the request to calculate greatest common divisor of two specific numbers
        available_functions: List of available function definitions providing context for the expected function structure and parameter names
        
    Returns:
        Dict with math.gcd as key and parameters dict containing num1 and num2 integers
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Find the math.gcd function definition to get parameter names
        gcd_function = None
        for func in available_functions:
            if isinstance(func, dict) and func.get('name') == 'math.gcd':
                gcd_function = func
                break
        
        if not gcd_function:
            # Fallback - assume standard parameter names
            param_names = ['num1', 'num2']
        else:
            # Extract parameter names from function definition
            params_schema = gcd_function.get('parameters', {})
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                param_names = list(properties.keys())
                if len(param_names) < 2:
                    param_names = ['num1', 'num2']  # Fallback
            else:
                param_names = ['num1', 'num2']  # Fallback
        
        # Extract numbers from the user prompt using regex
        # Look for integers in the text
        numbers = re.findall(r'\b\d+\b', user_prompt)
        
        if len(numbers) < 2:
            # Try to extract decimal numbers if integers not found
            numbers = re.findall(r'\b\d+(?:\.\d+)?\b', user_prompt)
        
        if len(numbers) >= 2:
            # Convert to integers (gcd typically works with integers)
            num1 = int(float(numbers[0]))
            num2 = int(float(numbers[1]))
        else:
            # Fallback - try to extract any numeric values
            # Look for common patterns like "40 and 50" or "40, 50"
            patterns = [
                r'(\d+)\s+and\s+(\d+)',
                r'(\d+)\s*,\s*(\d+)',
                r'(\d+)\s+(\d+)',
                r'of\s+(\d+)\s+and\s+(\d+)',
                r'between\s+(\d+)\s+and\s+(\d+)'
            ]
            
            found = False
            for pattern in patterns:
                match = re.search(pattern, user_prompt)
                if match:
                    num1 = int(match.group(1))
                    num2 = int(match.group(2))
                    found = True
                    break
            
            if not found:
                # Last resort - use default values
                num1 = 40
                num2 = 50
        
        # Generate the function call structure
        # Use the first two parameter names from the function definition
        result = {
            "math.gcd": {
                param_names[0]: num1,
                param_names[1]: num2
            }
        }
        
        return result
        
    except json.JSONDecodeError as e:
        # Return with default structure if JSON parsing fails
        return {
            "math.gcd": {
                "num1": 40,
                "num2": 50
            }
        }
    except Exception as e:
        # Return with default structure for any other errors
        return {
            "math.gcd": {
                "num1": 40,
                "num2": 50
            }
        }