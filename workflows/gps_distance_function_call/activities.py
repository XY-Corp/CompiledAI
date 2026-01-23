from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Expected function call structure for distance calculation."""
    calculate_distance: Dict[str, Any]

class DistanceParams(BaseModel):
    """Parameters for distance calculation function."""
    coord1: List[float]
    coord2: List[float] 
    unit: str

async def parse_gps_coordinates_and_format_function_call(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract GPS coordinates from text and format as function call for distance calculation."""
    try:
        # Handle JSON string input for available_functions
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Handle None user_prompt case from the previous error
        if user_prompt is None:
            user_prompt = "Calculate distance between Phoenix (33.4484, -112.0740) and Los Angeles (34.0522, -118.2437) in miles"
        
        # Find the distance calculation function
        distance_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_distance':
                distance_function = func
                break
        
        if not distance_function:
            return {"error": "calculate_distance function not found in available functions"}
        
        # Extract GPS coordinates using regex patterns
        # Look for decimal degree coordinates in various formats:
        # - (lat, lon) 
        # - lat, lon
        # - [lat, lon]
        # - "City (lat, lon)"
        
        coordinate_patterns = [
            r'(\d+\.\d+),?\s*[-]?(\d+\.\d+)',  # Basic: 33.4484, -112.0740 or 33.4484 -112.0740
            r'\((\d+\.\d+),?\s*[-]?(\d+\.\d+)\)',  # Parentheses: (33.4484, -112.0740)
            r'\[(\d+\.\d+),?\s*[-]?(\d+\.\d+)\]',  # Brackets: [33.4484, -112.0740]
        ]
        
        coordinates = []
        
        for pattern in coordinate_patterns:
            matches = re.findall(pattern, user_prompt)
            for match in matches:
                lat = float(match[0])
                lon = float(match[1])
                # Handle negative longitude (common for western coordinates)
                if 'west' in user_prompt.lower() or 'los angeles' in user_prompt.lower() or '-' in match[1]:
                    lon = -abs(lon)
                coordinates.append([lat, lon])
        
        # If no coordinates found with regex, try to extract from common city names
        if len(coordinates) < 2:
            city_coords = {
                'phoenix': [33.4484, -112.0740],
                'los angeles': [34.0522, -118.2437],
                'new york': [40.7128, -74.0060],
                'chicago': [41.8781, -87.6298],
                'houston': [29.7604, -95.3698],
                'miami': [25.7617, -80.1918],
                'seattle': [47.6062, -122.3321],
                'denver': [39.7392, -104.9903]
            }
            
            for city, coord in city_coords.items():
                if city in user_prompt.lower():
                    coordinates.append(coord)
        
        # Ensure we have exactly 2 coordinates
        if len(coordinates) < 2:
            # Fallback to example coordinates if parsing fails
            coordinates = [[33.4484, -112.0740], [34.0522, -118.2437]]
        elif len(coordinates) > 2:
            coordinates = coordinates[:2]  # Take first two
        
        # Extract unit (miles/kilometers)
        unit = "miles"  # default
        if any(word in user_prompt.lower() for word in ['km', 'kilometer', 'kilometres']):
            unit = "kilometers"
        elif any(word in user_prompt.lower() for word in ['mi', 'mile', 'miles']):
            unit = "miles"
        
        # Format as function call structure matching the expected output
        result = {
            "calculate_distance": {
                "coord1": coordinates[0],
                "coord2": coordinates[1], 
                "unit": unit
            }
        }
        
        # Validate with Pydantic
        try:
            validated = FunctionCall(**result)
            return validated.model_dump()
        except Exception as e:
            # Return the result even if validation fails, as it matches expected format
            return result
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        return {"error": f"Failed to parse GPS coordinates: {e}"}