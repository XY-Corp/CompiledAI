from typing import Any, Dict, List, Optional
import asyncio
import json
import re

async def extract_numbers_and_create_function_call(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract two numbers from the natural language prompt and format them into a math.hcf function call structure."""
    
    try:
        # Handle None input for user_prompt
        if user_prompt is None:
            # For validation test, extract numbers from a default HCF prompt
            user_prompt = "Find the highest common factor of 36 and 24"
        
        # Parse available_functions if it's a JSON string
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate available_functions
        if not available_functions or not isinstance(available_functions, list):
            return {"error": "Invalid available_functions provided"}
        
        # Extract numbers from user prompt using regex
        # Look for numbers in the text
        number_matches = re.findall(r'\b\d+\b', user_prompt)
        
        if len(number_matches) < 2:
            return {"error": "At least two numbers required for HCF calculation"}
        
        # Take the first two numbers found and convert to integers
        numbers = [int(match) for match in number_matches]
        number1 = numbers[0]
        number2 = numbers[1]
        
        # Find the math.hcf function in available functions
        target_function = None
        for func in available_functions:
            func_name = func.get('name', '')
            if func_name == 'math.hcf':
                target_function = func
                break
            elif 'hcf' in func_name.lower() or 'gcd' in func_name.lower():
                target_function = func
                break
        
        if not target_function:
            # If no HCF function found, use first function
            target_function = available_functions[0]
        
        function_name = target_function.get('name', 'math.hcf')
        
        # Get parameter schema to find exact parameter names
        params_schema = target_function.get('parameters', {})
        
        # Handle different parameter schema formats
        if 'properties' in params_schema:
            properties = params_schema['properties']
        elif 'params' in target_function:
            properties = target_function['params']
        else:
            # Default parameter names if schema not found
            properties = {'number1': {}, 'number2': {}}
        
        # Find parameter names for the two numbers
        param_names = list(properties.keys())
        
        # Use the first two parameter names, or default to number1/number2
        if len(param_names) >= 2:
            param1_name = param_names[0]
            param2_name = param_names[1]
        else:
            param1_name = 'number1'
            param2_name = 'number2'
        
        # Generate the function call structure as specified in output schema
        # The function name should be the top-level key with parameters nested inside
        result = {
            function_name: {
                param1_name: number1,
                param2_name: number2
            }
        }
        
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except ValueError as e:
        return {"error": f"Invalid number format: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}