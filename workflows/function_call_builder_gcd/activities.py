from typing import Any, Dict, List, Optional
import re
import json


async def build_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user prompt to extract the two numbers and build a function call structure for math.gcd.
    
    The prompt contains a request like 'Calculate the greatest common divisor of two numbers: X and Y'.
    Extract the numbers X and Y using regex pattern matching, then return the function call with 
    the function name as the top-level key.
    
    Args:
        prompt: The natural language prompt containing the GCD calculation request with two numbers to extract
        functions: List of available function definitions to understand the expected parameter structure
        
    Returns:
        Dict with math.gcd as key and parameters dict containing num1 and num2 integers.
        Example: {"math.gcd": {"num1": 40, "num2": 50}}
    """
    try:
        # Handle JSON string input defensively for functions
        if isinstance(functions, str):
            try:
                functions = json.loads(functions)
            except json.JSONDecodeError:
                pass
        
        # Handle JSON string input defensively for prompt
        if isinstance(prompt, str):
            # Check if it's a JSON string that needs parsing
            if prompt.startswith('{') or prompt.startswith('"'):
                try:
                    parsed_prompt = json.loads(prompt)
                    if isinstance(parsed_prompt, dict):
                        prompt = parsed_prompt.get('prompt', str(parsed_prompt))
                    elif isinstance(parsed_prompt, str):
                        prompt = parsed_prompt
                except json.JSONDecodeError:
                    pass  # Keep as regular string
        
        # Ensure prompt is a string
        prompt_text = str(prompt)
        
        # Extract numbers from the user prompt using multiple regex patterns
        # Order from most specific to least specific
        patterns = [
            # "Calculate the greatest common divisor of two numbers: 40 and 50"
            r'(?:two\s+numbers?)[:.]?\s*(\d+)\s+and\s+(\d+)',
            # "GCD of 40 and 50" or "greatest common divisor of 40 and 50"
            r'(?:gcd|greatest\s+common\s+divisor)\s+(?:of\s+)?(\d+)\s+and\s+(\d+)',
            # "find the GCD of 40 and 50"
            r'(?:find|calculate|compute|get).*?(?:gcd|greatest\s+common\s+divisor).*?(\d+)\s+and\s+(\d+)',
            # "of 40 and 50"
            r'of\s+(\d+)\s+and\s+(\d+)',
            # "40 and 50" pattern
            r'(\d+)\s+and\s+(\d+)',
            # "between 40 and 50"
            r'between\s+(\d+)\s+and\s+(\d+)',
            # "40, 50" comma separated
            r'(\d+)\s*,\s*(\d+)',
            # Just two numbers with space
            r'(\d+)\s+(\d+)',
        ]
        
        num1, num2 = None, None
        
        # Try each pattern until we find a match
        for pattern in patterns:
            match = re.search(pattern, prompt_text, re.IGNORECASE)
            if match:
                num1 = int(match.group(1))
                num2 = int(match.group(2))
                break
        
        # If no pattern matched, extract all numbers and take the first two
        if num1 is None or num2 is None:
            numbers = re.findall(r'\b\d+\b', prompt_text)
            if len(numbers) >= 2:
                num1 = int(numbers[0])
                num2 = int(numbers[1])
            elif len(numbers) == 1:
                # Only one number found, use it for both
                num1 = int(numbers[0])
                num2 = 1
            else:
                # No numbers found, use default values
                num1 = 0
                num2 = 0
        
        # Return the function call structure with math.gcd as top-level key
        return {
            "math.gcd": {
                "num1": num1,
                "num2": num2
            }
        }
        
    except Exception:
        # Return with default structure for any errors
        return {
            "math.gcd": {
                "num1": 0,
                "num2": 0
            }
        }
