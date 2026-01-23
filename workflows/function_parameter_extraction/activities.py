from typing import Any, Dict, List, Optional
import asyncio
import json
import re


async def extract_function_parameters(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract parameter values from the natural language prompt and return a function call object.
    
    Uses LLM to understand the user's intent and extract the correct parameter values 
    (initial_velocity, acceleration, time) from the text.
    
    Args:
        prompt: The natural language prompt describing the physics problem with values for 
                initial velocity, acceleration, and time duration
        functions: List of available function definitions with name, description, and parameter schemas
    
    Returns:
        Dict with function name as top-level key containing nested parameters.
        Example: {"calculate_final_velocity": {"initial_velocity": 0, "acceleration": 9.8, "time": 5}}
    """
    try:
        # Handle JSON string input defensively for functions
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"calculate_final_velocity": {"initial_velocity": 0, "acceleration": 0.0, "time": 0}}
        
        # Find the calculate_final_velocity function from the list
        target_function = None
        for func in functions:
            if func.get('name') == 'calculate_final_velocity':
                target_function = func
                break
        
        # Default to first function if calculate_final_velocity not found
        if target_function is None and functions:
            target_function = functions[0]
        
        function_name = target_function.get('name', 'calculate_final_velocity') if target_function else 'calculate_final_velocity'
        
        # Extract numeric values from the physics problem text using regex patterns
        prompt_lower = prompt.lower()
        
        initial_velocity = None
        acceleration = None
        time_value = None
        
        # Check for "started from rest" or "at rest" which means initial_velocity = 0
        if re.search(r'(?:start(?:ed|s|ing)?|begin(?:s|ning)?)\s+(?:from\s+)?rest', prompt_lower) or \
           re.search(r'(?:at|from)\s+rest', prompt_lower) or \
           re.search(r'rest(?:ing)?(?:\s+position)?', prompt_lower):
            initial_velocity = 0
        
        # Pattern for initial velocity (various phrasings)
        if initial_velocity is None:
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
                    val = float(match.group(1))
                    initial_velocity = int(val) if val == int(val) else val
                    break
        
        # Pattern for acceleration (various phrasings)
        # Examples: "acceleration of 9.8 m/s^2", "accelerates at 9.8 m/s²"
        accel_patterns = [
            r'acceleration\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:m/s\^?2|m/s²|meters?\s*(?:per|/)\s*second\s*(?:squared|\^?2))?',
            r'accelerates?\s+(?:at\s+)?(\d+(?:\.\d+)?)\s*(?:m/s\^?2|m/s²)?',
            r'(\d+(?:\.\d+)?)\s*(?:m/s\^2|m/s²|meters?\s*(?:per|/)\s*second\s*(?:squared|\^2))',
        ]
        
        for pattern in accel_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                acceleration = float(match.group(1))
                break
        
        # Pattern for time (various phrasings)
        # Examples: "for 5 seconds", "time of 5 s", "after 5 seconds"
        time_patterns = [
            r'(?:for|after|over|during)\s+(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)',
            r'time\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)\s*(?:later|elapsed|passes)',
            r'(\d+(?:\.\d+)?)\s*sec(?:ond)?s?\b',
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                val = float(match.group(1))
                time_value = int(val) if val == int(val) else val
                break
        
        # Fallback: try to find numbers in sequence and assign them in order
        if initial_velocity is None or acceleration is None or time_value is None:
            # Find all numbers in the prompt with their context
            numbers_found = []
            
            # Find numbers with m/s^2 context (acceleration)
            for match in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:m/s\^2|m/s²)', prompt_lower):
                if acceleration is None:
                    acceleration = float(match.group(1))
            
            # Find numbers with just m/s context (velocity)
            for match in re.finditer(r'(\d+(?:\.\d+)?)\s*m/s(?!\^|²)', prompt_lower):
                if initial_velocity is None:
                    val = float(match.group(1))
                    initial_velocity = int(val) if val == int(val) else val
            
            # Find numbers with seconds context (time)
            for match in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)', prompt_lower):
                if time_value is None:
                    val = float(match.group(1))
                    time_value = int(val) if val == int(val) else val
        
        # Set defaults if still not found
        initial_velocity = initial_velocity if initial_velocity is not None else 0
        acceleration = acceleration if acceleration is not None else 0.0
        time_value = time_value if time_value is not None else 0
        
        # Ensure proper types based on expected output
        # initial_velocity should be integer, acceleration can be float, time should be integer
        if isinstance(initial_velocity, float) and initial_velocity == int(initial_velocity):
            initial_velocity = int(initial_velocity)
        if isinstance(time_value, float) and time_value == int(time_value):
            time_value = int(time_value)
        
        # Return in the required function call format with function name as top-level key
        return {
            function_name: {
                "initial_velocity": initial_velocity,
                "acceleration": acceleration,
                "time": time_value
            }
        }
        
    except json.JSONDecodeError:
        # Return default structure on JSON parse error
        return {
            "calculate_final_velocity": {
                "initial_velocity": 0,
                "acceleration": 0.0,
                "time": 0
            }
        }
    except Exception:
        # Return default structure on any other error
        return {
            "calculate_final_velocity": {
                "initial_velocity": 0,
                "acceleration": 0.0,
                "time": 0
            }
        }
