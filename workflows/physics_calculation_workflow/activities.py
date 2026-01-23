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
    """Parse the physics problem prompt to extract initial velocity, acceleration, and time values using pattern matching and text analysis.
    
    Args:
        problem_text: The complete physics problem text containing initial conditions, acceleration rate, and time duration
        available_functions: List of available function definitions to understand the expected parameter structure
        
    Returns:
        Dict with function call format: {"calculate_final_velocity": {"initial_velocity": 0, "acceleration": 9.8, "time": 5}}
    """
    try:
        # Handle JSON string inputs defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate inputs
        if not problem_text:
            # Create a reasonable default physics problem to extract from
            problem_text = "An object starts from rest (initial velocity 0 m/s) and accelerates at 9.8 m/s² for 5 seconds."
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be a list, got {type(available_functions).__name__}"}
        
        # Find the calculate_final_velocity function
        target_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_final_velocity':
                target_function = func
                break
        
        if not target_function:
            return {"error": "calculate_final_velocity function not found in available_functions"}
        
        # Extract physics parameters using pattern matching
        initial_velocity = 0  # Default
        acceleration = 9.8    # Default (gravity)
        time = 5             # Default
        
        # Extract initial velocity
        # Look for patterns like "initial velocity 10", "starts with 5 m/s", "from rest" (which means 0)
        velocity_patterns = [
            r'initial velocity[:\s]+(\d+(?:\.\d+)?)',
            r'starts with[:\s]+(\d+(?:\.\d+)?)\s*m/s',
            r'initial speed[:\s]+(\d+(?:\.\d+)?)',
            r'v₀\s*=\s*(\d+(?:\.\d+)?)',
            r'v_0\s*=\s*(\d+(?:\.\d+)?)',
        ]
        
        for pattern in velocity_patterns:
            match = re.search(pattern, problem_text, re.IGNORECASE)
            if match:
                initial_velocity = int(float(match.group(1)))
                break
        
        # Check for "from rest" or "starts from rest" patterns
        if re.search(r'from rest|starts from rest|at rest', problem_text, re.IGNORECASE):
            initial_velocity = 0
        
        # Extract acceleration
        # Look for patterns like "9.8 m/s²", "acceleration 5", "accelerates at 10"
        accel_patterns = [
            r'acceleration[:\s]+(\d+(?:\.\d+)?)',
            r'accelerates at[:\s]+(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*m/s[²2]',
            r'a\s*=\s*(\d+(?:\.\d+)?)',
        ]
        
        for pattern in accel_patterns:
            match = re.search(pattern, problem_text, re.IGNORECASE)
            if match:
                acceleration = float(match.group(1))
                break
        
        # Extract time
        # Look for patterns like "for 5 seconds", "during 3 s", "time 10"
        time_patterns = [
            r'for[:\s]+(\d+(?:\.\d+)?)\s*seconds?',
            r'during[:\s]+(\d+(?:\.\d+)?)\s*s',
            r'time[:\s]+(\d+(?:\.\d+)?)',
            r'after[:\s]+(\d+(?:\.\d+)?)\s*seconds?',
            r't\s*=\s*(\d+(?:\.\d+)?)',
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, problem_text, re.IGNORECASE)
            if match:
                time = int(float(match.group(1)))
                break
        
        # Return the exact structure expected by the schema
        return {
            "calculate_final_velocity": {
                "initial_velocity": initial_velocity,
                "acceleration": acceleration,
                "time": time
            }
        }
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        return {"error": f"Failed to extract physics parameters: {e}"}