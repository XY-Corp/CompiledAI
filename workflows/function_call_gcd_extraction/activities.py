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
    """Extract two integers from the user prompt and construct a function call object for the number_theory.gcd function.
    
    The activity parses the prompt to find the two numbers mentioned, and returns them in the format
    required for a function call.
    
    Args:
        prompt: The natural language prompt containing a request to find the GCD of two numbers,
                e.g., 'Find the GCD of 36 and 48'
        functions: List of available function definitions with names, descriptions and parameter schemas
                   that can be called
        
    Returns:
        Dict with number_theory.gcd as key and parameters dict containing number1 and number2 integers.
        Example: {"number_theory.gcd": {"number1": 36, "number2": 48}}
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
            # "Find the GCD of 36 and 48" or "GCD of 36 and 48"
            r'(?:gcd|greatest\s+common\s+divisor)\s+(?:of\s+)?(\d+)\s+and\s+(\d+)',
            # "find the GCD of 36 and 48"
            r'(?:find|calculate|compute|get).*?(?:gcd|greatest\s+common\s+divisor).*?(\d+)\s+and\s+(\d+)',
            # "Calculate the greatest common divisor of two numbers: 36 and 48"
            r'(?:two\s+numbers?)[:.]?\s*(\d+)\s+and\s+(\d+)',
            # "of 36 and 48"
            r'of\s+(\d+)\s+and\s+(\d+)',
            # "36 and 48" pattern
            r'(\d+)\s+and\s+(\d+)',
            # "between 36 and 48"
            r'between\s+(\d+)\s+and\s+(\d+)',
            # "36, 48" comma separated
            r'(\d+)\s*,\s*(\d+)',
            # Just two numbers with space
            r'(\d+)\s+(\d+)',
        ]
        
        number1, number2 = None, None
        
        # Try each pattern until we find a match
        for pattern in patterns:
            match = re.search(pattern, prompt_text, re.IGNORECASE)
            if match:
                number1 = int(match.group(1))
                number2 = int(match.group(2))
                break
        
        # If no pattern matched, extract all numbers and take the first two
        if number1 is None or number2 is None:
            numbers = re.findall(r'\b\d+\b', prompt_text)
            if len(numbers) >= 2:
                number1 = int(numbers[0])
                number2 = int(numbers[1])
            elif len(numbers) == 1:
                # Only one number found, use it for both
                number1 = int(numbers[0])
                number2 = 1
            else:
                # No numbers found, use default values
                number1 = 0
                number2 = 0
        
        # Return the function call structure with number_theory.gcd as top-level key
        return {
            "number_theory.gcd": {
                "number1": number1,
                "number2": number2
            }
        }
        
    except Exception:
        # Return with default structure for any errors
        return {
            "number_theory.gcd": {
                "number1": 0,
                "number2": 0
            }
        }
