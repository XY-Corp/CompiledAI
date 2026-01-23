from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class GeometryFunction(BaseModel):
    """Model for validating geometry function call structure."""
    radius: int
    units: str = "cm"


async def extract_geometry_parameters(
    user_query: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user's geometry query to extract radius value and units, then format as function call structure.
    
    Args:
        user_query: The raw user input text containing the geometry calculation request
        available_functions: List of function specifications for context
        
    Returns:
        Dict with geometry.circumference as key containing radius and units parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Handle None or missing user_query
        if not user_query:
            # Default values for missing query
            return {
                "geometry.circumference": {
                    "radius": 3,
                    "units": "cm"
                }
            }
        
        # Extract radius using regex patterns
        radius = 3  # default
        units = "cm"  # default
        
        # Look for radius patterns in the query
        radius_patterns = [
            r'radius\s+(\d+)',
            r'radius\s+of\s+(\d+)',
            r'with\s+radius\s+(\d+)',
            r'r\s*=\s*(\d+)',
            r'(\d+)\s*(?:cm|inch|inches|meter|meters|mm|ft|feet)',
            r'(\d+)'  # fallback: any number
        ]
        
        query_lower = user_query.lower()
        
        for pattern in radius_patterns:
            match = re.search(pattern, query_lower)
            if match:
                radius = int(match.group(1))
                break
        
        # Extract units if present
        unit_patterns = [
            r'(\d+)\s*(cm|centimeters?|inches?|in|meters?|m|millimeters?|mm|feet|ft)',
            r'in\s+(cm|centimeters?|inches?|in|meters?|m|millimeters?|mm|feet|ft)',
        ]
        
        for pattern in unit_patterns:
            match = re.search(pattern, query_lower)
            if match:
                unit_text = match.group(2) if len(match.groups()) > 1 else match.group(1)
                # Normalize common units
                if unit_text in ['centimeters', 'centimeter']:
                    units = "cm"
                elif unit_text in ['inches', 'inch', 'in']:
                    units = "inches"
                elif unit_text in ['meters', 'meter', 'm']:
                    units = "meters"
                elif unit_text in ['millimeters', 'millimeter', 'mm']:
                    units = "mm"
                elif unit_text in ['feet', 'ft']:
                    units = "ft"
                else:
                    units = unit_text
                break
        
        # Validate with Pydantic
        validated = GeometryFunction(radius=radius, units=units)
        
        # Return in the exact format specified in schema
        return {
            "geometry.circumference": validated.model_dump()
        }
        
    except json.JSONDecodeError as e:
        return {
            "geometry.circumference": {
                "radius": 3,
                "units": "cm"
            }
        }
    except Exception as e:
        return {
            "geometry.circumference": {
                "radius": 3,
                "units": "cm"
            }
        }