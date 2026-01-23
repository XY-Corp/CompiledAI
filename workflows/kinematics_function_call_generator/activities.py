from typing import Any, Dict, List, Optional
import json
import re


async def extract_kinematics_parameters(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract kinematics parameters (acceleration, distance, initial_velocity) from a natural language physics question and format them as a function call object.
    
    Args:
        prompt: The natural language physics question asking about velocity/kinematics, containing acceleration and distance values to extract
        functions: List of available function definitions with their parameter schemas
    
    Returns:
        Dict with 'kinematics.final_velocity_from_distance' as the key containing nested parameters:
        {"kinematics.final_velocity_from_distance": {"acceleration": 4, "distance": 300}}
    """
    try:
        # Handle JSON string input defensively for functions
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        # Extract numeric values from the physics problem text using regex patterns
        acceleration = None
        distance = None
        initial_velocity = None
        
        # Normalize the prompt for easier parsing
        prompt_lower = prompt.lower()
        
        # Pattern for acceleration (various phrasings)
        # Examples: "acceleration of 4 m/s^2", "accelerates at 4 m/s²", "4 m/s^2 acceleration"
        accel_patterns = [
            r'acceleration\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'accelerates?\s+(?:at\s+)?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:m/s\^?2|m/s²|meters?\s*(?:per|/)\s*second\s*(?:squared|\^?2))',
            r'(\d+(?:\.\d+)?)\s*m/s\s*\^?\s*2',
        ]
        
        for pattern in accel_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                acceleration = int(float(match.group(1)))
                break
        
        # Pattern for distance (various phrasings)
        # Examples: "distance of 300 m", "300 meters", "travels 300 m", "over 300 meters"
        distance_patterns = [
            r'distance\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:m\b|meters?|metres?)',
            r'(?:travels?|covers?|over|across)\s+(?:a\s+)?(?:distance\s+(?:of\s+)?)?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:m|meters?)\s+(?:distance|away|far)',
        ]
        
        for pattern in distance_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                candidate = int(float(match.group(1)))
                # Avoid confusing acceleration value with distance
                # Distance values are typically larger than acceleration in these problems
                if acceleration is None or candidate != acceleration:
                    distance = candidate
                    break
        
        # Pattern for initial velocity (optional)
        # Examples: "initial velocity of 0 m/s", "starts at 5 m/s", "starting from rest"
        initial_vel_patterns = [
            r'initial\s+velocity\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'initial\s+speed\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'starts?\s+(?:at|with)\s+(?:a\s+)?(?:velocity\s+(?:of\s+)?)?(\d+(?:\.\d+)?)\s*(?:m/s|meters?\s*(?:per|/)\s*second)',
            r'beginning\s+(?:at|with)\s+(\d+(?:\.\d+)?)\s*(?:m/s)?',
            r'(\d+(?:\.\d+)?)\s*m/s\s*(?:initial|starting)',
        ]
        
        # Check for "from rest" or "at rest" which implies initial_velocity = 0
        if re.search(r'(?:from|at)\s+rest', prompt_lower) or re.search(r'starts?\s+(?:from\s+)?rest', prompt_lower):
            initial_velocity = 0.0
        else:
            for pattern in initial_vel_patterns:
                match = re.search(pattern, prompt_lower)
                if match:
                    initial_velocity = float(match.group(1))
                    break
        
        # Fallback: try to find numbers and assign based on context
        if acceleration is None or distance is None:
            # Find all numbers in the prompt
            numbers = re.findall(r'(\d+(?:\.\d+)?)', prompt)
            numbers = [float(n) for n in numbers]
            
            # Filter out already assigned values
            remaining_numbers = []
            for num in numbers:
                if acceleration is not None and int(num) == acceleration:
                    continue
                if distance is not None and int(num) == distance:
                    continue
                if initial_velocity is not None and num == initial_velocity:
                    continue
                remaining_numbers.append(num)
            
            # Sort remaining numbers - typically distance > acceleration
            remaining_numbers_sorted = sorted(remaining_numbers, reverse=True)
            
            idx = 0
            if distance is None and idx < len(remaining_numbers_sorted):
                distance = int(remaining_numbers_sorted[idx])
                idx += 1
            if acceleration is None and idx < len(remaining_numbers_sorted):
                acceleration = int(remaining_numbers_sorted[idx])
        
        # Build the result object
        result = {
            "kinematics.final_velocity_from_distance": {
                "acceleration": acceleration if acceleration is not None else 0,
                "distance": distance if distance is not None else 0
            }
        }
        
        # Only include initial_velocity if it was explicitly found in the prompt
        if initial_velocity is not None:
            result["kinematics.final_velocity_from_distance"]["initial_velocity"] = initial_velocity
        
        return result
        
    except json.JSONDecodeError:
        # Return default structure on JSON parse error
        return {
            "kinematics.final_velocity_from_distance": {
                "acceleration": 0,
                "distance": 0
            }
        }
    except Exception:
        # Return default structure on any other error
        return {
            "kinematics.final_velocity_from_distance": {
                "acceleration": 0,
                "distance": 0
            }
        }
