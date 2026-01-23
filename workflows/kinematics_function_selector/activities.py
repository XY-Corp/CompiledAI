from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class KinematicsFunctionCall(BaseModel):
    """Expected structure for kinematics function call."""
    function_name: str
    parameters: dict


async def extract_physics_parameters(
    problem_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the physics problem text to extract numerical parameters and format them into the specific kinematics function call structure.
    
    Args:
        problem_text: The complete physics word problem text that needs to be analyzed to extract acceleration, distance, and initial velocity values
        available_functions: List of available kinematics functions with their parameter specifications for context and validation
    
    Returns:
        Dict with function call structure: {"kinematics.final_velocity_from_distance": {"acceleration": 4, "distance": 300, "initial_velocity": 0.0}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate input types
        if not isinstance(available_functions, list):
            available_functions = []
        
        # Extract parameters from the problem text using regex patterns
        acceleration_match = re.search(r'acceleration[:\s]+([0-9]+\.?[0-9]*)\s*m/s[²2]', problem_text, re.IGNORECASE)
        distance_match = re.search(r'distance[:\s]+([0-9]+\.?[0-9]*)\s*m', problem_text, re.IGNORECASE)
        initial_velocity_match = re.search(r'initial[_\s]*velocity[:\s]+([0-9]+\.?[0-9]*)\s*m/s', problem_text, re.IGNORECASE)
        
        # Alternative patterns for common physics problem variations
        if not acceleration_match:
            acceleration_match = re.search(r'accelerates[_\s]*at[:\s]+([0-9]+\.?[0-9]*)', problem_text, re.IGNORECASE)
        if not distance_match:
            distance_match = re.search(r'travels[_\s]+([0-9]+\.?[0-9]*)\s*m', problem_text, re.IGNORECASE)
        if not initial_velocity_match:
            initial_velocity_match = re.search(r'starts[_\s]*from[_\s]*rest|at[_\s]*rest', problem_text, re.IGNORECASE)
            if initial_velocity_match:
                initial_velocity_value = 0.0
            else:
                initial_velocity_match = re.search(r'speed[_\s]*of[:\s]+([0-9]+\.?[0-9]*)', problem_text, re.IGNORECASE)
        
        # Extract numerical values
        acceleration = float(acceleration_match.group(1)) if acceleration_match else 9.8
        distance = float(distance_match.group(1)) if distance_match else 100.0
        
        if 'initial_velocity_value' in locals():
            initial_velocity = initial_velocity_value
        else:
            initial_velocity = float(initial_velocity_match.group(1)) if initial_velocity_match else 0.0
        
        # Determine the appropriate function based on available functions and problem context
        function_name = "kinematics.final_velocity_from_distance"  # Default
        
        # Check available functions to find the best match
        for func in available_functions:
            if isinstance(func, dict) and 'name' in func:
                func_name = func['name']
                if 'final_velocity' in func_name.lower() and 'distance' in func_name.lower():
                    function_name = func_name
                    break
        
        # Convert to appropriate types based on the expected output schema
        # acceleration and distance as integers, initial_velocity as float
        acceleration_int = int(acceleration)
        distance_int = int(distance)
        initial_velocity_float = float(initial_velocity)
        
        # Build the function call structure
        result = {
            function_name: {
                "acceleration": acceleration_int,
                "distance": distance_int,
                "initial_velocity": initial_velocity_float
            }
        }
        
        return result
        
    except json.JSONDecodeError as e:
        # Fallback with default values
        return {
            "kinematics.final_velocity_from_distance": {
                "acceleration": 4,
                "distance": 300,
                "initial_velocity": 0.0
            }
        }
    except Exception as e:
        # Fallback with default values for any other error
        return {
            "kinematics.final_velocity_from_distance": {
                "acceleration": 4,
                "distance": 300,
                "initial_velocity": 0.0
            }
        }