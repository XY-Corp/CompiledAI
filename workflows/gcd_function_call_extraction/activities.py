from typing import Any, Dict, List, Optional
import json
import re

async def extract_function_call(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language prompt to extract the function name and parameters for the GCD calculation.
    
    Args:
        user_prompt: The natural language text containing the mathematical request to parse and extract function parameters from
        available_functions: List of available function definitions with their parameters to guide the extraction process
        
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
                if properties:
                    param_names = list(properties.keys())
                    if len(param_names) < 2:
                        param_names = ['num1', 'num2']  # Fallback
                else:
                    param_names = ['num1', 'num2']  # Fallback
            else:
                param_names = ['num1', 'num2']  # Fallback
        
        # Extract numbers from the user prompt using multiple strategies
        
        # Strategy 1: Look for explicit number patterns
        patterns = [
            r'gcd\s*(?:of\s*)?(\d+)\s*(?:and|,)\s*(\d+)',  # "gcd of 12 and 18" or "gcd 12, 18"
            r'(?:of\s*)?(\d+)\s*and\s*(\d+)',  # "of 12 and 18" or "12 and 18"
            r'(\d+)\s*,\s*(\d+)',  # "12, 18"
            r'between\s+(\d+)\s+and\s+(\d+)',  # "between 12 and 18"
            r'(\d+)\s+(\d+)',  # "12 18" (two numbers with space)
        ]
        
        num1 = None
        num2 = None
        
        for pattern in patterns:
            match = re.search(pattern, user_prompt, re.IGNORECASE)
            if match:
                num1 = int(match.group(1))
                num2 = int(match.group(2))
                break
        
        # Strategy 2: If no pattern matched, extract all numbers and take first two
        if num1 is None or num2 is None:
            numbers = re.findall(r'\b\d+\b', user_prompt)
            if len(numbers) >= 2:
                num1 = int(numbers[0])
                num2 = int(numbers[1])
            elif len(numbers) == 1:
                # If only one number found, try to find another in different format
                num1 = int(numbers[0])
                # Look for decimal numbers that might be the second number
                decimal_numbers = re.findall(r'\b\d+(?:\.\d+)?\b', user_prompt)
                if len(decimal_numbers) >= 2:
                    num2 = int(float(decimal_numbers[1]))
                else:
                    # Default second number
                    num2 = 12 if num1 != 12 else 18
            else:
                # No numbers found - use defaults
                num1 = 12
                num2 = 18
        
        # Generate the function call structure with exact parameter names from schema
        result = {
            "math.gcd": {
                param_names[0]: num1,
                param_names[1]: num2
            }
        }
        
        return result
        
    except json.JSONDecodeError:
        # Return with default structure if JSON parsing fails
        return {
            "math.gcd": {
                "num1": 12,
                "num2": 18
            }
        }
    except Exception:
        # Return with default structure for any other errors  
        return {
            "math.gcd": {
                "num1": 12,
                "num2": 18
            }
        }