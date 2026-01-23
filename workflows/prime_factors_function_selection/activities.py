from typing import Any, Dict, List, Optional
import json
import re

async def analyze_and_map_function(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user prompt to extract the number and maps it to the get_prime_factors function with appropriate parameters.
    
    Args:
        user_prompt: The natural language request containing the number for which prime factors need to be calculated
        available_functions: List of available functions with their descriptions and parameter requirements
        
    Returns:
        Dict with get_prime_factors as key and parameters object containing number and formatted fields
    """
    try:
        # Handle JSON string inputs defensively
        if isinstance(user_prompt, str) and user_prompt.strip().startswith('{'):
            try:
                parsed_prompt = json.loads(user_prompt)
                if isinstance(parsed_prompt, dict):
                    # Extract the actual request text from parsed dict if present
                    user_prompt = parsed_prompt.get('user_prompt', parsed_prompt.get('text', user_prompt))
            except json.JSONDecodeError:
                pass  # Continue with original string
        
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Extract numbers from the user prompt using deterministic regex patterns
        # Focus on prime factors-specific patterns first
        prime_factors_patterns = [
            r'prime\s+factors?\s+of\s+(\d+)',              # "prime factors of 450"
            r'factor\s+(\d+)\s+into\s+primes?',           # "factor 450 into primes"
            r'find\s+prime\s+factors?\s+of\s+(\d+)',      # "find prime factors of 450"
            r'(\d+)\s*prime\s+factors?',                  # "450 prime factors"
            r'prime\s+factorization\s+of\s+(\d+)',       # "prime factorization of 450"
            r'factorize\s+(\d+)\s+into\s+primes?',       # "factorize 450 into primes"
            r'what\s+are\s+the\s+prime\s+factors?\s+of\s+(\d+)', # "what are the prime factors of 450"
            r'decompose\s+(\d+)\s+into\s+primes?',       # "decompose 450 into primes"
            r'break\s+down\s+(\d+)\s+into\s+primes?',    # "break down 450 into primes"
            r'(\d+)\s+into\s+prime\s+factors?',          # "450 into prime factors"
            r'get\s+prime\s+factors?\s+of?\s*(\d+)',     # "get prime factors of 450"
            r'calculate\s+prime\s+factors?\s+of?\s*(\d+)', # "calculate prime factors 450"
            r'prime\s+factors?\s+for\s+(\d+)',           # "prime factors for 450"
        ]
        
        extracted_number = None
        
        # Try prime factors-specific patterns first
        for pattern in prime_factors_patterns:
            match = re.search(pattern, user_prompt, re.IGNORECASE)
            if match:
                try:
                    extracted_number = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
        
        # If no prime factors-specific pattern found, look for any number in the text
        if extracted_number is None:
            # Find all numbers in the text
            number_matches = re.findall(r'\b(\d+)\b', user_prompt)
            if number_matches:
                # Take the first number found
                try:
                    extracted_number = int(number_matches[0])
                except ValueError:
                    pass
        
        # Default to 0 if no number found
        if extracted_number is None:
            extracted_number = 0
        
        # Determine if formatted output is requested
        # Look for keywords that suggest formatted output preference
        formatted_keywords = [
            r'formatted?',
            r'pretty',
            r'nicely?',
            r'readable',
            r'display',
            r'show',
            r'list',
            r'format',
        ]
        
        formatted = True  # Default to true for better user experience
        
        # Check if user specifically asks for raw/unformatted output
        unformatted_keywords = [
            r'raw',
            r'unformatted?',
            r'plain',
            r'simple',
            r'basic',
            r'no\s+format',
        ]
        
        for keyword in unformatted_keywords:
            if re.search(keyword, user_prompt, re.IGNORECASE):
                formatted = False
                break
        
        # Return in the exact format specified by the schema
        return {
            "get_prime_factors": {
                "number": extracted_number,
                "formatted": formatted
            }
        }
        
    except Exception as e:
        # Return default structure on error to match schema
        return {
            "get_prime_factors": {
                "number": 0,
                "formatted": True
            }
        }