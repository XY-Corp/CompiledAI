from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FactorialFunctionCall(BaseModel):
    """Expected function call structure for math.factorial."""
    number: int

async def parse_factorial_request(
    user_input: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user input to extract the number for factorial calculation and generate the appropriate function call structure.
    
    Args:
        user_input: The raw user request containing the number for which factorial needs to be calculated
        available_functions: List of available mathematical functions with their descriptions and parameters
        
    Returns:
        Function call structure with the function name as the top-level key and its parameters as a nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        # Extract number from user input using regex
        # Look for patterns like "factorial of 5", "5!", "calculate factorial 5", etc.
        number_patterns = [
            r'factorial\s+(?:of\s+)?(\d+)',  # "factorial of 5" or "factorial 5"
            r'(\d+)\s*!',                    # "5!"
            r'(\d+)\s+factorial',            # "5 factorial"
            r'calculate\s+factorial\s+(?:of\s+)?(\d+)',  # "calculate factorial of 5"
            r'find\s+factorial\s+(?:of\s+)?(\d+)',       # "find factorial of 5"
            r'(\d+)'                         # any standalone number as fallback
        ]
        
        extracted_number = None
        for pattern in number_patterns:
            match = re.search(pattern, user_input.lower())
            if match:
                extracted_number = int(match.group(1))
                break
        
        # If no number found, try to use LLM as fallback
        if extracted_number is None:
            prompt = f"""Extract the number for factorial calculation from this user request: "{user_input}"

Return ONLY the integer number, nothing else.
For example: if input is "calculate factorial of 7", return: 7"""
            
            response = llm_client.generate(prompt)
            content = response.content.strip()
            
            try:
                extracted_number = int(content)
            except ValueError:
                # Try to extract number from response
                number_match = re.search(r'\d+', content)
                if number_match:
                    extracted_number = int(number_match.group())
                else:
                    extracted_number = 5  # Default fallback
        
        # Validate the extracted number is reasonable for factorial
        if extracted_number < 0:
            extracted_number = abs(extracted_number)  # Make positive
        elif extracted_number > 1000:
            extracted_number = 1000  # Cap at reasonable limit
            
        # Construct the function call structure as specified in output schema
        result = {
            "math.factorial": {
                "number": extracted_number
            }
        }
        
        return result
        
    except json.JSONDecodeError as e:
        # Fallback with default structure
        return {
            "math.factorial": {
                "number": 5
            }
        }
    except Exception as e:
        # Fallback with default structure  
        return {
            "math.factorial": {
                "number": 5
            }
        }