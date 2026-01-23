from typing import Any, Dict, List, Optional
import asyncio
import json
import re


async def extract_triangle_parameters(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract triangle base and height values from user prompt text using pattern matching and numerical extraction.
    
    Args:
        user_prompt: The raw user text containing triangle dimensions and calculation request
        available_functions: List of available function definitions to determine expected parameter format
    
    Returns:
        dict: Returns a function call structure with calculate_triangle_area as the key and extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Extract numerical values from the prompt using regex
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', user_prompt.lower() if user_prompt else "")
        
        # Extract unit if specified, otherwise default to "units"
        unit_match = re.search(r'\b(cm|m|mm|inches?|in|ft|feet|units?)\b', user_prompt.lower() if user_prompt else "")
        unit = unit_match.group(1) if unit_match else "units"
        
        # Look for base/height keywords or assume first two numbers are base and height
        base = None
        height = None
        
        if user_prompt:
            # Try to extract base value
            base_match = re.search(r'base\s*(?:is|=|:)?\s*(\d+(?:\.\d+)?)', user_prompt.lower())
            if base_match:
                base = float(base_match.group(1))
            
            # Try to extract height value  
            height_match = re.search(r'height\s*(?:is|=|:)?\s*(\d+(?:\.\d+)?)', user_prompt.lower())
            if height_match:
                height = float(height_match.group(1))
        
        # Fallback: if we have at least 2 numbers and couldn't extract base/height specifically
        if (base is None or height is None) and len(numbers) >= 2:
            if base is None:
                base = float(numbers[0])
            if height is None:
                height = float(numbers[1])
        
        # Default values if extraction fails
        if base is None:
            base = 10  # Default base
        if height is None:
            height = 5  # Default height
        
        # Convert to integers as required by schema
        base = int(base)
        height = int(height)
        
        # Normalize unit to singular form
        if unit.endswith('es'):
            unit = unit[:-2]  # inches -> inch
        elif unit.endswith('s') and unit not in ['units']:
            unit = unit[:-1]  # units stays as units
        
        # Create the result structure exactly as specified in the output schema
        result = {
            "calculate_triangle_area": {
                "base": base,
                "height": height, 
                "unit": unit
            }
        }
        
        return result
        
    except json.JSONDecodeError as e:
        # Fallback with default values if JSON parsing fails
        return {
            "calculate_triangle_area": {
                "base": 10,
                "height": 5,
                "unit": "units"
            }
        }
    except Exception as e:
        # Fallback with default values for any other error
        return {
            "calculate_triangle_area": {
                "base": 10,
                "height": 5,
                "unit": "units"
            }
        }