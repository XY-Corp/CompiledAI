from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

async def extract_factorial_parameters(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses the user request to extract the number for factorial calculation and formats as a function call.
    
    Args:
        user_request: The raw user input containing the factorial calculation request with the number to calculate
        available_functions: List of available math functions with their parameter schemas and descriptions
        
    Returns:
        Dict with math.factorial as key and parameters object containing the number field
    """
    try:
        # Handle JSON string inputs defensively
        if isinstance(user_request, str) and user_request.strip().startswith('{'):
            try:
                parsed_request = json.loads(user_request)
                if isinstance(parsed_request, dict):
                    # Extract the actual request text from parsed dict if present
                    user_request = parsed_request.get('user_request', parsed_request.get('text', user_request))
            except json.JSONDecodeError:
                pass  # Continue with original string
        
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Extract numbers from the user request using deterministic regex patterns
        # Focus on factorial-specific patterns first
        factorial_patterns = [
            r'factorial\s+of\s+(\d+)',           # "factorial of 5"
            r'(\d+)\s*factorial',                # "5 factorial"  
            r'factorial\s*\(\s*(\d+)\s*\)',      # "factorial(5)"
            r'(\d+)\s*!',                        # "5!"
            r'calculate\s+factorial\s+of?\s*(\d+)', # "calculate factorial of 5"
            r'find\s+factorial\s+of\s+(\d+)',    # "find factorial of 5"
            r'what\s+is\s+(\d+)\s*factorial',    # "what is 5 factorial"
            r'what\s+is\s+factorial\s+of\s+(\d+)', # "what is factorial of 5"
            r'compute\s+factorial\s+of?\s*(\d+)', # "compute factorial 5"
            r'(\d+)\s+fact',                     # "5 fact"
        ]
        
        extracted_number = None
        
        # Try factorial-specific patterns first
        for pattern in factorial_patterns:
            match = re.search(pattern, user_request, re.IGNORECASE)
            if match:
                try:
                    extracted_number = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
        
        # If no factorial-specific pattern found, look for any number in the text
        if extracted_number is None:
            # Find all numbers in the text
            number_matches = re.findall(r'\b(\d+)\b', user_request)
            if number_matches:
                # Take the first number found
                try:
                    extracted_number = int(number_matches[0])
                except ValueError:
                    pass
        
        # Default to 0 if no number found
        if extracted_number is None:
            extracted_number = 0
        
        # Return in the exact format specified by the schema
        return {
            "math.factorial": {
                "number": extracted_number
            }
        }
        
    except Exception as e:
        # Return default structure on error to match schema
        return {
            "math.factorial": {
                "number": 0
            }
        }