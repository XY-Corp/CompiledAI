from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel, Field

class FunctionCall(BaseModel):
    """Model for the structured function call result."""
    calculate_triangle_area: dict = Field(..., description="Parameters for triangle area calculation")

async def parse_triangle_function_call(
    user_input: str,
    available_functions: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts triangle parameters from user query and generates structured function call for calculate_triangle_area.
    
    Args:
        user_input: The raw user query text containing triangle base, height, and potentially unit information
        available_functions: The JSON specification of available functions for parameter validation
        
    Returns:
        Dict with function name as key and parameters as nested values
    """
    try:
        # Parse available functions if it's a JSON string
        if isinstance(available_functions, str):
            functions_data = json.loads(available_functions)
        else:
            functions_data = available_functions
            
        # Find the calculate_triangle_area function schema
        triangle_function = None
        if isinstance(functions_data, list):
            for func in functions_data:
                if func.get('name') == 'calculate_triangle_area':
                    triangle_function = func
                    break
        elif isinstance(functions_data, dict) and functions_data.get('name') == 'calculate_triangle_area':
            triangle_function = functions_data
            
        if not triangle_function:
            return {"calculate_triangle_area": {"error": "calculate_triangle_area function not found"}}
            
        # Extract base value using regex patterns
        base_patterns = [
            r'base\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'base\s*[=:]\s*(\d+(?:\.\d+)?)',
            r'with\s+(?:a\s+)?base\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:unit[s]?)?\s+base',
        ]
        
        base_value = None
        for pattern in base_patterns:
            match = re.search(pattern, user_input.lower())
            if match:
                base_value = float(match.group(1))
                break
                
        # Extract height value using regex patterns
        height_patterns = [
            r'height\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'height\s*[=:]\s*(\d+(?:\.\d+)?)',
            r'and\s+height\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:unit[s]?)?\s+height',
        ]
        
        height_value = None
        for pattern in height_patterns:
            match = re.search(pattern, user_input.lower())
            if match:
                height_value = float(match.group(1))
                break
                
        # Extract unit information
        unit_patterns = [
            r'(\d+(?:\.\d+)?)\s+(unit[s]?|cm|m|ft|in|inches?|feet|meters?|centimeters?)',
            r'in\s+(unit[s]?|cm|m|ft|in|inches?|feet|meters?|centimeters?)',
            r'(\w+)\s+unit[s]?',
        ]
        
        unit_value = "units"  # default
        for pattern in unit_patterns:
            match = re.search(pattern, user_input.lower())
            if match:
                potential_unit = match.group(1) if len(match.groups()) == 1 else match.group(2)
                if potential_unit and not potential_unit.replace('.', '').isdigit():
                    unit_value = potential_unit
                    break
                    
        # If no specific unit found, look for common unit words
        common_units = ['units', 'cm', 'meters', 'feet', 'inches', 'm', 'ft', 'in']
        for unit in common_units:
            if unit in user_input.lower():
                unit_value = unit
                break
                
        # Construct the function call result
        parameters = {}
        
        if base_value is not None:
            parameters["base"] = base_value
        else:
            parameters["base"] = "<UNKNOWN>"
            
        if height_value is not None:
            parameters["height"] = height_value  
        else:
            parameters["height"] = "<UNKNOWN>"
            
        parameters["unit"] = unit_value
        
        # Return in the exact format specified by the output schema
        return {
            "calculate_triangle_area": parameters
        }
        
    except json.JSONDecodeError as e:
        return {"calculate_triangle_area": {"error": f"Invalid JSON in available_functions: {e}"}}
    except Exception as e:
        return {"calculate_triangle_area": {"error": f"Failed to parse triangle function call: {e}"}}