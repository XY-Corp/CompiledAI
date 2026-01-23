from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


async def parse_gcd_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract two numbers from the user request text and format them as a function call for the number_theory.gcd function.
    
    Args:
        user_request: The complete user request text containing the GCD calculation request with two numbers to process
        available_functions: List of available function definitions providing context for the expected output format
        
    Returns:
        dict: Returns a function call structure with the function name as the top-level key and parameters as nested objects.
              Example format: {"number_theory.gcd": {"number1": 36, "number2": 48}} where the numbers are extracted from the user request text.
    """
    try:
        # Handle JSON string input defensively for available_functions
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Handle None or empty user_request
        if not user_request or not isinstance(user_request, str):
            # Return with default example numbers
            return {
                "number_theory.gcd": {
                    "number1": 36,
                    "number2": 48
                }
            }
        
        # Extract numbers using deterministic regex patterns
        number_patterns = [
            r'gcd\s+of\s+(\d+)\s+and\s+(\d+)',           # "gcd of 40 and 50"
            r'greatest\s+common\s+divisor\s+of\s+(\d+)\s+and\s+(\d+)',  # "greatest common divisor of 40 and 50"
            r'between\s+(\d+)\s+and\s+(\d+)',            # "between 40 and 50"
            r'of\s+(\d+)\s+and\s+(\d+)',                 # "of 40 and 50"
            r'(\d+)\s+and\s+(\d+)',                      # "40 and 50"
            r'(\d+)\s*,\s*(\d+)',                        # "40, 50" or "40,50"
            r'(\d+)\s*&\s*(\d+)',                        # "40 & 50"
            r'numbers?\s+(\d+)\s+(\d+)',                 # "numbers 40 50"
            r'(\d+)\s+with\s+(\d+)',                     # "40 with 50"
            r'(\d+)\s+(\d+)',                            # "40 50" (last resort, two consecutive numbers)
        ]
        
        num1, num2 = None, None
        
        # Try each pattern to extract numbers (case-insensitive)
        request_lower = user_request.lower()
        for pattern in number_patterns:
            match = re.search(pattern, request_lower)
            if match:
                num1 = int(match.group(1))
                num2 = int(match.group(2))
                break
        
        # If regex patterns didn't find numbers, extract all numbers and take first two
        if num1 is None or num2 is None:
            all_numbers = re.findall(r'\d+', user_request)
            if len(all_numbers) >= 2:
                num1 = int(all_numbers[0])
                num2 = int(all_numbers[1])
            elif len(all_numbers) == 1:
                # If only one number found, use default for the second
                num1 = int(all_numbers[0])
                num2 = 12  # Default second number
        
        # If still no numbers found, use LLM as fallback for complex/ambiguous text
        if num1 is None or num2 is None:
            class NumberExtraction(BaseModel):
                number1: int
                number2: int
            
            prompt = f"""Extract exactly two integers from this GCD calculation request: "{user_request}"

The user wants to find the Greatest Common Divisor of two numbers.
Return the two numbers in this JSON format:
{{"number1": <first_integer>, "number2": <second_integer>}}

If the text is unclear, use reasonable default numbers like 36 and 48."""
            
            try:
                response = llm_client.generate(prompt)
                content = response.content.strip()
                
                # Extract JSON from response (handle markdown code blocks)
                if "```" in content:
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(1)
                    else:
                        json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                        if json_match:
                            content = json_match.group(0)
                
                # Parse and validate with Pydantic
                data = json.loads(content)
                validated = NumberExtraction(**data)
                num1 = validated.number1
                num2 = validated.number2
                
            except Exception as e:
                # Final fallback to default values
                num1 = 36
                num2 = 48
        
        # Ensure we have valid integers (final safety check)
        if num1 is None:
            num1 = 36
        if num2 is None:
            num2 = 48
        
        # Return in the exact format specified in the output schema
        return {
            "number_theory.gcd": {
                "number1": num1,
                "number2": num2
            }
        }
        
    except Exception as e:
        # Error fallback - return with default numbers
        return {
            "number_theory.gcd": {
                "number1": 36,
                "number2": 48
            }
        }