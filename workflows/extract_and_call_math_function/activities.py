from typing import Any, Dict, List, Optional
import re
import json


async def extract_factorial_number(
    user_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract the number from the user prompt for factorial calculation using deterministic parsing.
    
    Args:
        user_text: The complete user prompt text containing the factorial calculation request with the number to extract
        
    Returns:
        Dict with math.factorial containing the extracted number parameter as integer
    """
    try:
        # Parse JSON string input defensively if needed
        if isinstance(user_text, str) and user_text.startswith('{'):
            try:
                parsed_input = json.loads(user_text)
                if isinstance(parsed_input, dict) and 'user_text' in parsed_input:
                    user_text = parsed_input['user_text']
            except json.JSONDecodeError:
                pass  # Continue with original string
        
        # Extract numbers from the text using regex patterns
        # Look for factorial-related patterns first
        factorial_patterns = [
            r'factorial\s+of\s+(\d+)',
            r'(\d+)\s*factorial',
            r'factorial\s*\(\s*(\d+)\s*\)',
            r'(\d+)\s*!',
            r'calculate\s+factorial\s+(\d+)',
            r'find\s+factorial\s+of\s+(\d+)',
            r'what\s+is\s+(\d+)\s*factorial',
            r'what\s+is\s+factorial\s+of\s+(\d+)',
        ]
        
        extracted_number = None
        
        # Try factorial-specific patterns first
        for pattern in factorial_patterns:
            match = re.search(pattern, user_text, re.IGNORECASE)
            if match:
                try:
                    extracted_number = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
        
        # If no factorial-specific pattern found, look for any number in the text
        if extracted_number is None:
            # Find all numbers in the text
            number_matches = re.findall(r'\b(\d+)\b', user_text)
            if number_matches:
                # Take the first number found
                try:
                    extracted_number = int(number_matches[0])
                except ValueError:
                    pass
        
        # Default fallback if no number found
        if extracted_number is None:
            extracted_number = 0
        
        # Return in the exact format specified by the schema
        return {
            "math.factorial": {
                "number": extracted_number
            }
        }
        
    except Exception as e:
        # Return default structure on error
        return {
            "math.factorial": {
                "number": 0
            }
        }