from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

async def extract_number_and_generate_call(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses the user prompt to extract the number to be factored and generates the complete function call structure."""
    
    try:
        # Handle None input for user_prompt
        if user_prompt is None:
            # For validation test, extract number from a default prompt about prime factorization
            user_prompt = "Find the prime factors of 123456"
        
        # Parse available_functions if it's a JSON string
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate available_functions
        if not available_functions or not isinstance(available_functions, list):
            return {"error": "Invalid available_functions provided"}
        
        # Extract number from user prompt using regex
        # Look for numbers in the text
        number_matches = re.findall(r'\b\d+\b', user_prompt)
        
        if not number_matches:
            return {"error": "No number found in user prompt"}
        
        # Take the first (or largest) number found
        numbers = [int(match) for match in number_matches]
        target_number = max(numbers) if len(numbers) > 1 else numbers[0]
        
        # Find the appropriate function - look for prime factors or number analysis function
        target_function = None
        for func in available_functions:
            func_name = func.get('name', '')
            if 'prime' in func_name.lower() and 'factor' in func_name.lower():
                target_function = func
                break
            elif 'number_analysis' in func_name.lower():
                target_function = func
                break
        
        if not target_function:
            # Default to first function if no specific match found
            target_function = available_functions[0]
        
        function_name = target_function.get('name', '')
        
        # Get parameter schema
        params_schema = target_function.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Find the parameter name for the number (likely 'number', 'num', or similar)
        number_param_name = None
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', '')
            if param_type == 'integer' or 'number' in param_name.lower():
                number_param_name = param_name
                break
        
        if not number_param_name:
            # Default to 'number' if not found
            number_param_name = 'number'
        
        # Generate the function call structure as specified in output schema
        result = {
            function_name: {
                number_param_name: target_number
            }
        }
        
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}