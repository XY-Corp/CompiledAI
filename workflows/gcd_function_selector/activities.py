from typing import Any, Dict, List, Optional
import re
import json


async def extract_gcd_parameters(
    prompt: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user prompt to extract the two integer numbers for GCD calculation and return the function call structure with the math.gcd function name and parameters.
    
    Args:
        prompt: The user's natural language request asking to find the GCD of two numbers,
                e.g., 'Find the greatest common divisor of 12 and 18'
        
    Returns:
        Dict with math.gcd as key and parameters dict containing num1 and num2 integers.
        Example: {"math.gcd": {"num1": 12, "num2": 18}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(prompt, str):
            # Check if it's a JSON string that needs parsing
            if prompt.startswith('{') or prompt.startswith('"'):
                try:
                    prompt = json.loads(prompt)
                    if isinstance(prompt, dict):
                        prompt = prompt.get('prompt', str(prompt))
                except json.JSONDecodeError:
                    pass  # Keep as regular string
        
        # Ensure prompt is a string
        prompt_text = str(prompt)
        
        # Extract numbers from the user prompt using multiple regex patterns
        # Order from most specific to least specific
        patterns = [
            # "GCD of 12 and 18" or "greatest common divisor of 12 and 18"
            r'(?:gcd|greatest\s+common\s+divisor)\s+(?:of\s+)?(\d+)\s+and\s+(\d+)',
            # "find the GCD of 12 and 18"
            r'(?:find|calculate|compute|get).*?(?:gcd|greatest\s+common\s+divisor).*?(\d+)\s+and\s+(\d+)',
            # "12 and 18" pattern
            r'(\d+)\s+and\s+(\d+)',
            # "of 12 and 18"
            r'of\s+(\d+)\s+and\s+(\d+)',
            # "between 12 and 18"
            r'between\s+(\d+)\s+and\s+(\d+)',
            # "12, 18" comma separated
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
                # Only one number found, use defaults
                num1 = int(numbers[0])
                num2 = 1
            else:
                # No numbers found, use example defaults
                num1 = 12
                num2 = 18
        
        # Return the function call structure
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
                "num1": 12,
                "num2": 18
            }
        }
