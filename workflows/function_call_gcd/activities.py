from typing import Any, Dict, List, Optional
import json
import re


async def extract_gcd_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract the two numbers from the natural language prompt and format them as a function call for math.gcd.
    
    Args:
        prompt: The natural language prompt containing a request to calculate GCD of two numbers
        functions: List of available function definitions with their names, descriptions, and parameter schemas
        
    Returns:
        Dict with math.gcd as key and parameters dict containing num1 and num2 integers
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        # Find the math.gcd function definition to get parameter names
        gcd_function = None
        for func in functions:
            if isinstance(func, dict) and func.get('name') == 'math.gcd':
                gcd_function = func
                break
        
        # Extract parameter names from function definition
        param_names = ['num1', 'num2']  # Default parameter names
        if gcd_function:
            params_schema = gcd_function.get('parameters', {})
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                if properties and len(properties) >= 2:
                    param_names = list(properties.keys())[:2]
        
        # Extract numbers from the prompt using multiple regex patterns
        # Try from most specific to least specific
        patterns = [
            r'(?:gcd|greatest common divisor).*?(?:of|between)\s+(\d+)\s+and\s+(\d+)',
            r'(?:calculate|find|compute).*?(?:gcd|greatest common divisor).*?(\d+)\s+and\s+(\d+)',
            r'(?:of|between)\s+(?:two\s+numbers[:\s]*)?(\d+)\s+and\s+(\d+)',
            r'numbers[:\s]+(\d+)\s+and\s+(\d+)',
            r'(\d+)\s+and\s+(\d+)',
            r'(\d+)\s*,\s*(\d+)',
            r'(\d+)\s+(\d+)',
        ]
        
        num1, num2 = None, None
        
        # Try each pattern until we find a match
        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                num1 = int(match.group(1))
                num2 = int(match.group(2))
                break
        
        # If no pattern matched, extract all numbers and take the first two
        if num1 is None or num2 is None:
            numbers = re.findall(r'\b\d+\b', prompt)
            if len(numbers) >= 2:
                num1 = int(numbers[0])
                num2 = int(numbers[1])
            else:
                # Fallback to default values if no numbers found
                num1 = 0
                num2 = 0
        
        # Return the function call structure with math.gcd as top-level key
        return {
            "math.gcd": {
                param_names[0]: num1,
                param_names[1]: num2
            }
        }
        
    except json.JSONDecodeError:
        # Return with default structure if JSON parsing fails
        return {
            "math.gcd": {
                "num1": 0,
                "num2": 0
            }
        }
    except Exception:
        # Return with default structure for any other errors
        return {
            "math.gcd": {
                "num1": 0,
                "num2": 0
            }
        }
