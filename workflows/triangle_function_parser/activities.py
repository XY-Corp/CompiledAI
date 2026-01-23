from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class TriangleParams(BaseModel):
    """Expected structure for triangle function parameters."""
    calculate_triangle_area: Dict[str, List[Any]]

async def parse_triangle_parameters(
    text: str,
    available_functions: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> List[Dict[str, Any]]:
    """Extract triangle calculation parameters from natural language text and format them according to the expected JSON structure.
    
    Args:
        text: The natural language text containing triangle calculation request with base and height values
        available_functions: JSON string of available function definitions to understand the expected parameter structure
    
    Returns:
        List containing the exact function call structure: [{"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units", ""]}}]
    """
    try:
        # Parse available functions JSON string
        if isinstance(available_functions, str):
            functions_data = json.loads(available_functions)
        else:
            functions_data = available_functions
        
        # Extract numerical values from text using regex
        # Look for patterns like "base of 10", "height of 5", "10 units", etc.
        base_patterns = [
            r'base\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s+(?:units?\s+)?base',
            r'base\s*[=:]\s*(\d+(?:\.\d+)?)'
        ]
        
        height_patterns = [
            r'height\s+(?:of\s+)?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s+(?:units?\s+)?height',
            r'height\s*[=:]\s*(\d+(?:\.\d+)?)'
        ]
        
        unit_patterns = [
            r'(\w+)\s+units?',
            r'in\s+(\w+)',
            r'(\w+)\s+(?:base|height)'
        ]
        
        # Extract base value
        base_value = None
        for pattern in base_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                base_value = float(match.group(1))
                break
        
        # Extract height value
        height_value = None
        for pattern in height_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                height_value = float(match.group(1))
                break
        
        # Extract unit (default to "units" if not found)
        unit_value = "units"
        for pattern in unit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                unit_candidate = match.group(1).lower()
                # Only use if it's a reasonable unit word (not "of", "the", etc.)
                if unit_candidate not in ['of', 'the', 'a', 'an', 'with', 'and']:
                    unit_value = unit_candidate
                break
        
        # Fallback: if no specific patterns found, try to extract any numbers in sequence
        if base_value is None or height_value is None:
            numbers = re.findall(r'\d+(?:\.\d+)?', text)
            if len(numbers) >= 2:
                if base_value is None:
                    base_value = float(numbers[0])
                if height_value is None:
                    height_value = float(numbers[1])
        
        # Default values if extraction failed
        if base_value is None:
            base_value = 0
        if height_value is None:
            height_value = 0
        
        # Convert to integers if they're whole numbers
        if base_value == int(base_value):
            base_value = int(base_value)
        if height_value == int(height_value):
            height_value = int(height_value)
        
        # Format according to the expected output structure:
        # [{"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units", ""]}}]
        result = [{
            "calculate_triangle_area": {
                "base": [base_value],
                "height": [height_value],
                "unit": [unit_value, ""]
            }
        }]
        
        return result
        
    except json.JSONDecodeError as e:
        # Return default structure with error indication
        return [{
            "calculate_triangle_area": {
                "base": [0],
                "height": [0],
                "unit": ["error", str(e)]
            }
        }]
    except Exception as e:
        # Return default structure with error indication
        return [{
            "calculate_triangle_area": {
                "base": [0],
                "height": [0],
                "unit": ["error", str(e)]
            }
        }]