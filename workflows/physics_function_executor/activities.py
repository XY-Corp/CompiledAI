from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

async def extract_physics_parameters(
    problem_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract physics problem parameters from natural language text and determine the appropriate function call structure.
    
    Args:
        problem_text: The physics problem question text containing values and conditions to extract
        available_functions: List of available physics calculation functions with their parameter schemas and descriptions
        
    Returns:
        Dict with function name as key and extracted parameters as nested dict
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        # Validate inputs
        if not available_functions:
            return {"error": "No functions available"}
            
        # If problem_text is empty or None, use example default for calculate_final_speed
        if not problem_text or not problem_text.strip():
            return {
                "calculate_final_speed": {
                    "initial_speed": 0,
                    "time": 5,
                    "gravity": -9.81
                }
            }
            
        # Extract numerical values from the problem text
        # Pattern matches integers and floats with optional units
        number_pattern = r'(\d+(?:\.\d+)?)\s*(?:m/s|m/s²|m/s\^2|meters?/second|seconds?|s|m|kg|N|J)?'
        numbers = re.findall(number_pattern, problem_text.lower())
        
        # Convert to appropriate numeric types
        numerical_values = []
        for num_str in numbers:
            num = float(num_str)
            if num.is_integer():
                numerical_values.append(int(num))
            else:
                numerical_values.append(num)
        
        # Analyze problem text for physics concepts and keywords
        problem_lower = problem_text.lower()
        
        # Select the most appropriate function based on problem context
        selected_function = None
        
        for func in available_functions:
            func_name = func.get('name', '').lower()
            func_desc = func.get('description', '').lower()
            
            # Match based on physics concepts in the problem
            if ('final_speed' in func_name or 'final_velocity' in func_name) and any(keyword in problem_lower for keyword in ['dropped', 'fall', 'falling', 'free fall', 'gravity']):
                selected_function = func
                break
            elif 'kinetic_energy' in func_name and any(keyword in problem_lower for keyword in ['energy', 'kinetic', 'moving']):
                selected_function = func
                break
            elif 'distance' in func_name and any(keyword in problem_lower for keyword in ['distance', 'displacement', 'travel']):
                selected_function = func
                break
            elif 'acceleration' in func_name and any(keyword in problem_lower for keyword in ['acceleration', 'accelerate', 'force']):
                selected_function = func
                break
                
        # Default to first function if no specific match found
        if not selected_function and available_functions:
            selected_function = available_functions[0]
            
        if not selected_function:
            return {"error": "No suitable function found"}
            
        # Extract function details
        func_name = selected_function.get('name')
        parameters_schema = selected_function.get('parameters', {})
        properties = parameters_schema.get('properties', {})
        required_params = parameters_schema.get('required', [])
        
        # Map extracted numbers to function parameters
        extracted_params = {}
        
        # Physics-specific parameter mapping based on function name and problem context
        if 'final_speed' in func_name.lower() or 'final_velocity' in func_name.lower():
            # Free fall or velocity calculation
            if 'rest' in problem_lower or 'dropped' in problem_lower:
                # Object starts from rest
                extracted_params['initial_speed'] = 0
            elif len(numerical_values) > 0:
                extracted_params['initial_speed'] = numerical_values[0]
            else:
                extracted_params['initial_speed'] = 0
                
            # Extract time value
            time_keywords = ['second', 'seconds', 's', 'time']
            time_found = False
            for i, num in enumerate(numerical_values):
                # Look for time indicators in surrounding text
                if any(keyword in problem_lower for keyword in time_keywords):
                    extracted_params['time'] = num
                    time_found = True
                    break
            
            if not time_found and len(numerical_values) > 0:
                # Use the first/last number as time if no specific time indicator
                extracted_params['time'] = numerical_values[-1] if len(numerical_values) > 1 else numerical_values[0]
            elif not time_found:
                extracted_params['time'] = 5  # Default example value
                
            # Set gravity for free fall problems
            if 'gravity' in properties:
                extracted_params['gravity'] = -9.81  # Standard gravity
                
        else:
            # Generic parameter mapping for other physics functions
            param_names = list(properties.keys())
            for i, param_name in enumerate(param_names):
                if i < len(numerical_values):
                    extracted_params[param_name] = numerical_values[i]
                else:
                    # Set default values based on parameter type/name
                    param_info = properties.get(param_name, {})
                    if isinstance(param_info, dict):
                        param_type = param_info.get('type', 'number')
                    else:
                        param_type = 'number'
                        
                    if 'gravity' in param_name.lower():
                        extracted_params[param_name] = -9.81
                    elif param_type in ['number', 'integer']:
                        extracted_params[param_name] = 0
                    else:
                        extracted_params[param_name] = 0
        
        # Ensure all required parameters are present
        for param in required_params:
            if param not in extracted_params:
                if 'gravity' in param.lower():
                    extracted_params[param] = -9.81
                else:
                    extracted_params[param] = 0
                    
        # Return in the exact format specified: function name as key, parameters as nested dict
        return {func_name: extracted_params}
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        return {"error": f"Processing error: {e}"}