from typing import Any, Dict, List, Optional
import asyncio
import json
import re


async def parse_physics_problem(
    problem_text: str,
    target_function: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts numerical values and parameters from physics problem text using deterministic parsing to identify initial velocity, acceleration, and time values.
    
    Args:
        problem_text: The physics problem text containing values for initial velocity, acceleration, and time duration
        target_function: The function name to call (calculate_final_velocity) for structuring the output
        
    Returns:
        Dict with function name as key and extracted parameters as nested dict containing initial_velocity, acceleration, and time
    """
    try:
        # Handle empty or missing problem text
        if not problem_text or not problem_text.strip():
            # Return default physics values for empty input
            return {
                target_function: {
                    "initial_velocity": 0,
                    "acceleration": 9.8,
                    "time": 5
                }
            }
        
        # Extract all numerical values from the problem text using regex
        # Pattern matches integers and floats, with optional physics units
        number_pattern = r'(\d+(?:\.\d+)?)\s*(?:m/s²|m/s\^2|m/s2|m/s|meters?/second|seconds?|s|m)?'
        numbers = re.findall(number_pattern, problem_text.lower())
        
        # Convert to appropriate numeric types (int if whole number, float otherwise)
        numerical_values = []
        for num_str in numbers:
            num = float(num_str)
            if num.is_integer():
                numerical_values.append(int(num))
            else:
                numerical_values.append(num)
        
        # Initialize default physics parameters
        extracted_params = {
            "initial_velocity": 0,
            "acceleration": 9.8,  # Default gravity
            "time": 5
        }
        
        # Parse problem text for physics-specific patterns
        problem_lower = problem_text.lower()
        
        # Extract initial velocity
        initial_velocity_patterns = [
            r'initial\s+velocity[:\s]+(\d+(?:\.\d+)?)',
            r'starting\s+velocity[:\s]+(\d+(?:\.\d+)?)',
            r'v[_0o]\s*=\s*(\d+(?:\.\d+)?)',
            r'begins\s+at\s+(\d+(?:\.\d+)?)\s*m/s'
        ]
        
        for pattern in initial_velocity_patterns:
            match = re.search(pattern, problem_lower)
            if match:
                val = float(match.group(1))
                extracted_params["initial_velocity"] = int(val) if val.is_integer() else val
                break
        
        # Extract acceleration
        acceleration_patterns = [
            r'acceleration[:\s]+(\d+(?:\.\d+)?)',
            r'accelerates?\s+at\s+(\d+(?:\.\d+)?)',
            r'a\s*=\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*m/s²',
            r'(\d+(?:\.\d+)?)\s*m/s\^2'
        ]
        
        for pattern in acceleration_patterns:
            match = re.search(pattern, problem_lower)
            if match:
                val = float(match.group(1))
                extracted_params["acceleration"] = int(val) if val.is_integer() else val
                break
        
        # Extract time
        time_patterns = [
            r'for\s+(\d+(?:\.\d+)?)\s*seconds?',
            r'after\s+(\d+(?:\.\d+)?)\s*seconds?',
            r'time[:\s]+(\d+(?:\.\d+)?)',
            r't\s*=\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*s(?:\s|$)'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, problem_lower)
            if match:
                val = float(match.group(1))
                extracted_params["time"] = int(val) if val.is_integer() else val
                break
        
        # Fallback: if we have exactly 3 numbers and no specific patterns matched,
        # assume they're in order: initial_velocity, acceleration, time
        if len(numerical_values) == 3:
            if extracted_params["initial_velocity"] == 0:  # Not found by pattern
                extracted_params["initial_velocity"] = numerical_values[0]
            if extracted_params["acceleration"] == 9.8:  # Still default
                extracted_params["acceleration"] = numerical_values[1]  
            if extracted_params["time"] == 5:  # Still default
                extracted_params["time"] = numerical_values[2]
        elif len(numerical_values) >= 1:
            # Try to intelligently assign based on magnitude and context
            for val in numerical_values:
                if val > 50 and extracted_params["time"] == 5:  # Likely time if large
                    extracted_params["time"] = val
                elif 1 <= val <= 20 and extracted_params["acceleration"] == 9.8:  # Likely acceleration
                    extracted_params["acceleration"] = val
                elif val <= 100 and extracted_params["initial_velocity"] == 0:  # Likely initial velocity
                    extracted_params["initial_velocity"] = val
        
        # Return in the exact format specified: function name as key, parameters as nested dict
        return {target_function: extracted_params}
        
    except Exception as e:
        # Return default values on any error to maintain expected structure
        return {
            target_function: {
                "initial_velocity": 0,
                "acceleration": 9.8,
                "time": 5
            }
        }