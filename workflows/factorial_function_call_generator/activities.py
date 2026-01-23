from typing import Any, Dict, List, Optional
import json
import re


async def generate_factorial_function_call(
    query_text: str,
    available_functions: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses the user query to extract the number for factorial calculation and generates the required function call JSON structure with math.factorial as the function name.
    
    Args:
        query_text: The user query text that contains the factorial calculation request and number to be extracted
        available_functions: String representation of available function definitions to ensure proper function selection and parameter mapping
        
    Returns:
        Dict with math.factorial as key containing the number parameter extracted from the query
    """
    try:
        # Parse available_functions if it's a JSON string
        if isinstance(available_functions, str):
            functions_data = json.loads(available_functions)
        else:
            functions_data = available_functions
            
        # Extract number from query text using regex patterns
        # Look for patterns like "factorial of 5", "5!", "factorial(5)", etc.
        patterns = [
            r'factorial\s+of\s+(\d+)',  # "factorial of 5"
            r'(\d+)\s*!',                # "5!"
            r'factorial\s*\(\s*(\d+)\s*\)',  # "factorial(5)"
            r'calculate\s+factorial\s+(\d+)',  # "calculate factorial 5"
            r'factorial\s+(\d+)',        # "factorial 5"
            r'(\d+)\s+factorial',        # "5 factorial"
            r'find\s+factorial\s+of\s+(\d+)',  # "find factorial of 5"
            r'get\s+factorial\s+(\d+)',  # "get factorial 5"
            r'compute\s+factorial\s+of\s+(\d+)',  # "compute factorial of 5"
            r'(\d+)\s*factorial',        # "5factorial"
        ]
        
        extracted_number = None
        for pattern in patterns:
            match = re.search(pattern, query_text, re.IGNORECASE)
            if match:
                extracted_number = int(match.group(1))
                break
        
        # If no pattern matched, try to find any number in the text as fallback
        if extracted_number is None:
            number_match = re.search(r'\b(\d+)\b', query_text)
            if number_match:
                extracted_number = int(number_match.group(1))
        
        # Default to 1 if no number found
        if extracted_number is None:
            extracted_number = 1
            
        # Generate the function call structure as specified in the output schema
        result = {
            "math.factorial": {
                "number": extracted_number
            }
        }
        
        return result
        
    except json.JSONDecodeError as e:
        # If available_functions parsing fails, still try to extract the number
        number_match = re.search(r'\b(\d+)\b', query_text)
        extracted_number = int(number_match.group(1)) if number_match else 1
        
        return {
            "math.factorial": {
                "number": extracted_number
            }
        }
    except Exception as e:
        # Fallback: return structure with default number
        return {
            "math.factorial": {
                "number": 1
            }
        }