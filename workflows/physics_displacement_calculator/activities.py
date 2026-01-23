from typing import Any, Dict, List, Optional
import asyncio
import json
import re


async def extract_physics_parameters(
    query_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user's physics query to extract initial velocity, acceleration, and time values using pattern matching.
    
    Args:
        query_text: The user's natural language physics query containing numerical values for velocity, acceleration, and time
    
    Returns:
        Dict containing extracted physics parameters with fields: initial_velocity (int), acceleration (float), time (int)
    """
    try:
        # Initialize default values
        initial_velocity = 0
        acceleration = 9.8  # Default gravity
        time = 1
        
        # Pattern to extract velocity (look for patterns like "initial velocity 10 m/s", "velocity of 15", "v0 = 20")
        velocity_patterns = [
            r'initial\s+velocity\s*(?:of\s*)?(\d+(?:\.\d+)?)',
            r'velocity\s*(?:of\s*)?(\d+(?:\.\d+)?)',
            r'v0?\s*=\s*(\d+(?:\.\d+)?)',
            r'starts?\s*(?:with\s*)?(?:velocity\s*)?(\d+(?:\.\d+)?)\s*m/s',
            r'(\d+(?:\.\d+)?)\s*m/s\s*initial',
        ]
        
        for pattern in velocity_patterns:
            match = re.search(pattern, query_text, re.IGNORECASE)
            if match:
                initial_velocity = int(float(match.group(1)))
                break
        
        # Pattern to extract acceleration (look for patterns like "acceleration 9.8", "a = 2.5", "accelerates at 5")
        accel_patterns = [
            r'acceleration\s*(?:of\s*)?(\d+(?:\.\d+)?)',
            r'accelerates?\s*(?:at\s*)?(\d+(?:\.\d+)?)',
            r'a\s*=\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*m/s[²2]',
            r'gravity\s*(?:of\s*)?(\d+(?:\.\d+)?)',
        ]
        
        for pattern in accel_patterns:
            match = re.search(pattern, query_text, re.IGNORECASE)
            if match:
                acceleration = float(match.group(1))
                break
        
        # Pattern to extract time (look for patterns like "time 5 seconds", "t = 3", "for 10 s")
        time_patterns = [
            r'time\s*(?:of\s*)?(\d+(?:\.\d+)?)',
            r'for\s*(\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?',
            r't\s*=\s*(\d+(?:\.\d+)?)',
            r'after\s*(\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?',
            r'(\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?(?:\s*later)?',
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, query_text, re.IGNORECASE)
            if match:
                time = int(float(match.group(1)))
                break
        
        # If no specific patterns found, try to extract any numbers and make educated guesses
        if initial_velocity == 0 and acceleration == 9.8 and time == 1:
            numbers = re.findall(r'(\d+(?:\.\d+)?)', query_text)
            if len(numbers) >= 3:
                # Assume first number is velocity, second is time, third is acceleration
                initial_velocity = int(float(numbers[0]))
                time = int(float(numbers[1]))
                acceleration = float(numbers[2])
            elif len(numbers) == 2:
                # Assume first is velocity, second is time
                initial_velocity = int(float(numbers[0]))
                time = int(float(numbers[1]))
            elif len(numbers) == 1:
                # Assume it's velocity
                initial_velocity = int(float(numbers[0]))
        
        return {
            "initial_velocity": initial_velocity,
            "acceleration": acceleration,
            "time": time
        }
        
    except Exception as e:
        # Return reasonable defaults on error
        return {
            "initial_velocity": 0,
            "acceleration": 9.8,
            "time": 1
        }


async def format_function_call(
    physics_params: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Format the extracted physics parameters into the required function call structure with calculate_displacement as the top-level key.
    
    Args:
        physics_params: Dictionary containing extracted physics parameters: initial_velocity, acceleration, and time
    
    Returns:
        Dict with function call structure: {"calculate_displacement": {"initial_velocity": 10, "time": 5, "acceleration": 9.8}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(physics_params, str):
            physics_params = json.loads(physics_params)
        
        # Validate input is a dict
        if not isinstance(physics_params, dict):
            physics_params = {
                "initial_velocity": 0,
                "acceleration": 9.8,
                "time": 1
            }
        
        # Extract parameters with defaults
        initial_velocity = physics_params.get("initial_velocity", 0)
        acceleration = physics_params.get("acceleration", 9.8)
        time = physics_params.get("time", 1)
        
        # Format into the required function call structure
        return {
            "calculate_displacement": {
                "initial_velocity": initial_velocity,
                "time": time,
                "acceleration": acceleration
            }
        }
        
    except json.JSONDecodeError as e:
        # Return default structure on JSON parse error
        return {
            "calculate_displacement": {
                "initial_velocity": 0,
                "time": 1,
                "acceleration": 9.8
            }
        }
    except Exception as e:
        # Return default structure on any other error
        return {
            "calculate_displacement": {
                "initial_velocity": 0,
                "time": 1,
                "acceleration": 9.8
            }
        }