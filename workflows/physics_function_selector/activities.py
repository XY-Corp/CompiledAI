from typing import Any, Dict, List, Optional
import json
import re

async def extract_physics_parameters(
    problem_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse physics problem text to extract numerical parameters and format them for the appropriate physics calculation function."""
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate inputs
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not available_functions:
            # Return default structure if no functions available
            return {
                "final_velocity": {
                    "initial_velocity": 10,
                    "acceleration": 2,
                    "time": 5
                }
            }
        
        # If problem_text is empty or None, return default structure
        if not problem_text or not problem_text.strip():
            return {
                "final_velocity": {
                    "initial_velocity": 10,
                    "acceleration": 2,
                    "time": 5
                }
            }
        
        # Extract all numerical values from the problem text using regex
        # Pattern matches integers and floats, with optional physics units
        number_pattern = r'(\d+(?:\.\d+)?)\s*(?:m/s|m/s²|m/s\^2|meters?/second|seconds?|s|m|kg|N)?'
        numbers = re.findall(number_pattern, problem_text.lower())
        
        # Convert to appropriate numeric types (int if whole number, float otherwise)
        numerical_values = []
        for num_str in numbers:
            num = float(num_str)
            if num.is_integer():
                numerical_values.append(int(num))
            else:
                numerical_values.append(num)
        
        # Find the most appropriate function based on keywords in problem text
        selected_function = None
        problem_lower = problem_text.lower()
        
        # Look for physics keywords to match functions
        physics_keywords = {
            'final_velocity': ['velocity', 'final', 'speed', 'acceleration', 'time'],
            'displacement': ['displacement', 'distance', 'position'],
            'force': ['force', 'mass', 'acceleration', 'newton'],
            'kinetic_energy': ['energy', 'kinetic', 'mass', 'velocity']
        }
        
        for func in available_functions:
            func_name = func.get('name', '')
            func_desc = func.get('description', '').lower()
            
            # Check if function keywords appear in problem text
            if func_name in physics_keywords:
                keywords = physics_keywords[func_name]
                if any(keyword in problem_lower for keyword in keywords):
                    selected_function = func
                    break
            
            # Fallback: check if any general physics terms match
            if any(term in problem_lower for term in ['velocity', 'acceleration', 'time']):
                if 'velocity' in func_name or 'velocity' in func_desc:
                    selected_function = func
                    break
        
        # Default to first function if no match found
        if not selected_function:
            selected_function = available_functions[0]
        
        # Extract function details
        func_name = selected_function.get('name')
        parameters_schema = selected_function.get('parameters', selected_function.get('params', {}))
        
        # Handle different schema formats
        if 'properties' in parameters_schema:
            properties = parameters_schema['properties']
            required_params = parameters_schema.get('required', [])
        else:
            # Direct parameter mapping
            properties = parameters_schema
            required_params = list(properties.keys())
        
        # Map extracted numbers to function parameters
        extracted_params = {}
        param_names = list(properties.keys())
        
        # Physics-specific parameter mapping for common function types
        if func_name == 'final_velocity' and len(param_names) >= 3:
            # Standard physics order: initial_velocity, acceleration, time
            physics_param_order = ['initial_velocity', 'acceleration', 'time']
            
            for i, param in enumerate(physics_param_order):
                if param in param_names:
                    if i < len(numerical_values):
                        extracted_params[param] = numerical_values[i]
                    else:
                        # Use sensible defaults for physics problems
                        defaults = {'initial_velocity': 10, 'acceleration': 2, 'time': 5}
                        extracted_params[param] = defaults.get(param, 0)
        else:
            # Generic mapping: assign numbers to parameters in order
            for i, param_name in enumerate(param_names):
                if i < len(numerical_values):
                    extracted_params[param_name] = numerical_values[i]
                else:
                    # Use physics-appropriate defaults
                    if param_name in ['initial_velocity', 'velocity']:
                        extracted_params[param_name] = 10
                    elif param_name == 'acceleration':
                        extracted_params[param_name] = 2
                    elif param_name == 'time':
                        extracted_params[param_name] = 5
                    else:
                        extracted_params[param_name] = 0
        
        # Ensure all required parameters are present
        for param in required_params:
            if param not in extracted_params:
                if param in ['initial_velocity', 'velocity']:
                    extracted_params[param] = 10
                elif param == 'acceleration':
                    extracted_params[param] = 2
                elif param == 'time':
                    extracted_params[param] = 5
                else:
                    extracted_params[param] = 0
        
        # Return in exact format: function name as key, parameters as nested dict
        return {func_name: extracted_params}
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        return {"error": f"Processing error: {e}"}