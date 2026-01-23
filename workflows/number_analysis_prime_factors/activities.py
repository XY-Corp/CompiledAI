from typing import Any, Dict, List, Optional
import re
import json

async def extract_number_from_prompt(
    prompt: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract the number to be factored from the user's natural language prompt.
    
    Args:
        prompt: The raw user input containing a request to find prime factors of a specific number
        
    Returns:
        Dict with 'number_analysis.prime_factors' containing the extracted number parameter
    """
    try:
        # Parse JSON string input defensively if needed
        if isinstance(prompt, str) and prompt.strip().startswith('{'):
            try:
                parsed_input = json.loads(prompt)
                if isinstance(parsed_input, dict) and 'prompt' in parsed_input:
                    prompt = parsed_input['prompt']
            except json.JSONDecodeError:
                pass  # Continue with original string
        
        # Extract numbers from the text using regex patterns
        # Look for prime factor-related patterns first
        prime_factor_patterns = [
            r'prime\s+factors?\s+of\s+(\d+)',
            r'factor\s+(\d+)\s+into\s+primes?',
            r'find\s+prime\s+factors?\s+of\s+(\d+)',
            r'what\s+are\s+the\s+prime\s+factors?\s+of\s+(\d+)',
            r'decompose\s+(\d+)\s+into\s+prime\s+factors?',
            r'prime\s+factorization\s+of\s+(\d+)',
            r'factorize\s+(\d+)',
            r'(\d+)\s+prime\s+factors?',
            r'prime\s+decomposition\s+of\s+(\d+)',
            r'break\s+down\s+(\d+)\s+into\s+primes?',
        ]
        
        extracted_number = None
        
        # Try prime factor-specific patterns first
        for pattern in prime_factor_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                try:
                    extracted_number = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
        
        # If no prime factor-specific pattern found, look for any number in the text
        if extracted_number is None:
            # Find all numbers in the text
            number_matches = re.findall(r'\b(\d+)\b', prompt)
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
            "number_analysis.prime_factors": {
                "number": extracted_number
            }
        }
        
    except Exception as e:
        # Return default structure on error
        return {
            "number_analysis.prime_factors": {
                "number": 0
            }
        }