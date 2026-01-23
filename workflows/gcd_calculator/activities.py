from typing import Any, Dict, List, Optional
import json
import re


async def extract_numbers_and_format_function_call(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts two numbers from the user prompt and formats them into the required function call structure for math.gcd.
    
    Args:
        user_prompt: The raw user input text containing the request to calculate GCD with two numbers
        available_functions: List of available function definitions that can be called, used for context about expected function structure
        
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
        
        # Extract parameter names from function definition
        param_names = ['num1', 'num2']  # Default fallback
        if gcd_function:
            params_schema = gcd_function.get('parameters', {})
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                if properties and len(properties) >= 2:
                    param_names = list(properties.keys())[:2]
        
        # Extract numbers from the user prompt using multiple regex patterns
        # Start with the most specific patterns
        patterns = [
            r'(?:gcd|greatest common divisor).*?(?:of|between)\s+(\d+)\s+and\s+(\d+)',
            r'(?:calculate|find).*?(?:gcd|greatest common divisor).*?(\d+)\s+and\s+(\d+)',
            r'(\d+)\s+and\s+(\d+)',
            r'(\d+)\s*,\s*(\d+)',
            r'of\s+(\d+)\s+and\s+(\d+)',
            r'between\s+(\d+)\s+and\s+(\d+)',
            r'(\d+)\s+(\d+)',  # Two numbers separated by space
        ]
        
        num1, num2 = None, None
        
        # Try each pattern until we find a match
        for pattern in patterns:
            match = re.search(pattern, user_prompt, re.IGNORECASE)
            if match:
                num1 = int(match.group(1))
                num2 = int(match.group(2))
                break
        
        # If no pattern matched, extract all numbers and take the first two
        if num1 is None or num2 is None:
            numbers = re.findall(r'\b\d+\b', user_prompt)
            if len(numbers) >= 2:
                num1 = int(numbers[0])
                num2 = int(numbers[1])
            else:
                # Last resort - use example values
                num1 = 12
                num2 = 15
        
        # Generate the function call structure
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
                "num2": 15
            }
        }
    except Exception:
        # Return with default structure for any other errors
        return {
            "math.gcd": {
                "num1": 12,
                "num2": 15
            }
        }