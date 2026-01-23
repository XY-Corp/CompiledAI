from typing import Any, Dict, List, Optional
import json
import re


async def extract_velocity_params(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract the numeric parameters (initial_velocity, acceleration, time) from a natural language physics problem description and return them in the final_velocity function call format.
    
    Args:
        prompt: The natural language physics problem describing a vehicle's motion with initial velocity, acceleration, and time values to extract
        functions: List of available function definitions with their parameter schemas
    
    Returns:
        Dict with 'final_velocity' as the top-level key containing nested parameters:
        {"final_velocity": {"initial_velocity": 10, "acceleration": 2, "time": 5}}
    """
    try:
        # Handle JSON string input defensively for functions
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        # Extract numeric values from the physics problem text using regex patterns
        # Look for common patterns for initial velocity, acceleration, and time
        
        initial_velocity = None
        acceleration = None
        time_value = None
        
        # Normalize the prompt for easier parsing
        prompt_lower = prompt.lower()
        
        # Pattern for initial velocity (various phrasings)
        # Examples: "initial velocity of 10 m/s", "starts at 10 m/s", "initial speed of 10"
        initial_vel_patterns = [
            r'initial\s+velocity\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'initial\s+speed\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'starts?\s+(?:at|with)\s+(?:a\s+)?(?:velocity\s+(?:of\s+)?)?(\d+(?:\.\d+)?)\s*(?:m/s|meters?\s*(?:per|/)\s*second)',
            r'beginning\s+(?:at|with)\s+(\d+(?:\.\d+)?)\s*(?:m/s)?',
            r'moving\s+at\s+(\d+(?:\.\d+)?)\s*(?:m/s)',
            r'(\d+(?:\.\d+)?)\s*m/s\s*(?:initial|starting)',
        ]
        
        for pattern in initial_vel_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                initial_velocity = int(float(match.group(1)))
                break
        
        # Pattern for acceleration (various phrasings)
        # Examples: "acceleration of 2 m/s^2", "accelerates at 2 m/s²"
        accel_patterns = [
            r'acceleration\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'accelerates?\s+(?:at\s+)?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:m/s\^?2|m/s²|meters?\s*(?:per|/)\s*second\s*(?:squared|\^?2))',
        ]
        
        for pattern in accel_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                acceleration = int(float(match.group(1)))
                break
        
        # Pattern for time (various phrasings)
        # Examples: "for 5 seconds", "time of 5 s", "after 5 seconds"
        time_patterns = [
            r'(?:for|after|over|during)\s+(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)',
            r'time\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)\s*(?:later|elapsed|passes)',
            r'(\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?\b',
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                time_value = int(float(match.group(1)))
                break
        
        # Fallback: try to find numbers in sequence and assign them in order
        # This handles cases like "10 m/s, 2 m/s^2, and 5 seconds"
        if initial_velocity is None or acceleration is None or time_value is None:
            # Find all numbers in the prompt
            numbers = re.findall(r'(\d+(?:\.\d+)?)', prompt)
            numbers = [int(float(n)) for n in numbers]
            
            # Try to assign unassigned values from numbers found
            remaining_numbers = []
            for num in numbers:
                if initial_velocity is not None and num == initial_velocity:
                    continue
                if acceleration is not None and num == acceleration:
                    continue
                if time_value is not None and num == time_value:
                    continue
                remaining_numbers.append(num)
            
            # Assign remaining values
            idx = 0
            if initial_velocity is None and idx < len(remaining_numbers):
                initial_velocity = remaining_numbers[idx]
                idx += 1
            if acceleration is None and idx < len(remaining_numbers):
                acceleration = remaining_numbers[idx]
                idx += 1
            if time_value is None and idx < len(remaining_numbers):
                time_value = remaining_numbers[idx]
        
        # Set defaults if still not found
        initial_velocity = initial_velocity if initial_velocity is not None else 0
        acceleration = acceleration if acceleration is not None else 0
        time_value = time_value if time_value is not None else 0
        
        # Return in the required function call format
        return {
            "final_velocity": {
                "initial_velocity": initial_velocity,
                "acceleration": acceleration,
                "time": time_value
            }
        }
        
    except json.JSONDecodeError:
        # Return default structure on JSON parse error
        return {
            "final_velocity": {
                "initial_velocity": 0,
                "acceleration": 0,
                "time": 0
            }
        }
    except Exception:
        # Return default structure on any other error
        return {
            "final_velocity": {
                "initial_velocity": 0,
                "acceleration": 0,
                "time": 0
            }
        }
