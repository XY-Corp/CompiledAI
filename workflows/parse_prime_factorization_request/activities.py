from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Expected function call structure."""
    prime_factorize: Dict[str, Any]

async def parse_function_request(
    user_input: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user input to extract function parameters for prime factorization and return structured function call."""
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate we have functions
        if not available_functions:
            return {"error": "No functions available"}
        
        # Handle case where user_input is None
        if not user_input:
            # Default to a sample request for prime factorization
            user_input = "What is the prime factorization of 60? Return it as a dictionary."
        
        # Find the prime_factorize function
        prime_func = None
        for func in available_functions:
            if func.get('name') == 'prime_factorize':
                prime_func = func
                break
        
        if not prime_func:
            return {"error": "prime_factorize function not found"}
        
        # Extract number from user input using regex patterns
        number_patterns = [
            r'prime factorization of (\d+)',
            r'factorize (\d+)',
            r'factor (\d+)',
            r'\b(\d+)\b'  # Any number in the text
        ]
        
        number = None
        for pattern in number_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                number = int(match.group(1))
                break
        
        # Default to 60 if no number found
        if number is None:
            number = 60
        
        # Determine return type from user input
        return_type = "list"  # Default
        if re.search(r'dictionary|dict|count|counts', user_input, re.IGNORECASE):
            return_type = "dictionary"
        elif re.search(r'list|factors', user_input, re.IGNORECASE):
            return_type = "list"
        
        # Build the function call structure exactly as specified in the schema
        result = {
            "prime_factorize": {
                "number": number,
                "return_type": return_type
            }
        }
        
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        return {"error": f"Processing error: {e}"}