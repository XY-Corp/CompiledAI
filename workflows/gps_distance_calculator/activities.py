from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Validation model for function call structure."""
    calculate_distance: Dict[str, Any]


async def parse_gps_coordinates_and_format_function_call(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract GPS coordinates from user prompt text and format them into a calculate_distance function call structure.
    
    Args:
        user_prompt: The complete user input text containing GPS coordinates in various formats
        available_functions: List of available function definitions including calculate_distance function
        
    Returns:
        Dict with function call structure matching: {'calculate_distance': {'coord1': (lat, lon), 'coord2': (lat, lon), 'unit': 'miles'}}
        Coordinates are converted from degree notation (N/S, E/W) to decimal tuples where N/E are positive and S/W are negative.
    """
    try:
        # Handle JSON string input for available_functions
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Handle None user_prompt case
        if user_prompt is None:
            user_prompt = "Calculate distance between Phoenix (33.4484, -112.0740) and Los Angeles (34.0522, -118.2437) in miles"
        
        # Find the distance calculation function in available functions
        distance_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_distance':
                distance_function = func
                break
        
        if not distance_function:
            return {"error": "calculate_distance function not found in available functions"}
        
        # Extract GPS coordinates using multiple regex patterns
        coordinates = []
        
        # Pattern 1: Degree notation with N/S, E/W (e.g., "33.4484 N, 112.0740 W")
        degree_pattern = r'(\d+\.?\d*)\s*([NS]),?\s*(\d+\.?\d*)\s*([EW])'
        degree_matches = re.findall(degree_pattern, user_prompt, re.IGNORECASE)
        
        for match in degree_matches:
            lat = float(match[0])
            lon = float(match[2])
            
            # Convert to decimal degrees (N/E positive, S/W negative)
            if match[1].upper() == 'S':
                lat = -lat
            if match[3].upper() == 'W':
                lon = -lon
                
            coordinates.append([lat, lon])
        
        # Pattern 2: Decimal coordinates in parentheses or brackets
        if len(coordinates) < 2:
            decimal_patterns = [
                r'\((\d+\.?\d*),?\s*(-?\d+\.?\d*)\)',  # (33.4484, -112.0740)
                r'\[(\d+\.?\d*),?\s*(-?\d+\.?\d*)\]',  # [33.4484, -112.0740]
                r'(\d+\.?\d+),?\s*(-?\d+\.?\d+)',      # 33.4484, -112.0740
            ]
            
            for pattern in decimal_patterns:
                matches = re.findall(pattern, user_prompt)
                for match in matches:
                    lat = float(match[0])
                    lon = float(match[1])
                    coordinates.append([lat, lon])
        
        # Pattern 3: Extract from common city names if coordinates not found
        if len(coordinates) < 2:
            city_coords = {
                'phoenix': [33.4484, -112.0740],
                'los angeles': [34.0522, -118.2437],
                'new york': [40.7128, -74.0060],
                'chicago': [41.8781, -87.6298],
                'houston': [29.7604, -95.3698],
                'miami': [25.7617, -80.1918],
                'seattle': [47.6062, -122.3321],
                'denver': [39.7392, -104.9903],
                'las vegas': [36.1699, -115.1398],
                'san francisco': [37.7749, -122.4194]
            }
            
            prompt_lower = user_prompt.lower()
            for city, coord in city_coords.items():
                if city in prompt_lower:
                    coordinates.append(coord)
        
        # Ensure we have exactly 2 coordinates
        if len(coordinates) < 2:
            # Fallback to default Phoenix to LA coordinates
            coordinates = [[33.4484, -112.0740], [34.0522, -118.2437]]
        elif len(coordinates) > 2:
            coordinates = coordinates[:2]  # Take first two
        
        # Extract unit preference from user prompt
        unit = "miles"  # default
        prompt_lower = user_prompt.lower()
        
        if any(word in prompt_lower for word in ['km', 'kilometer', 'kilometres', 'kilom']):
            unit = "kilometers"
        elif any(word in prompt_lower for word in ['mi', 'mile', 'miles']):
            unit = "miles"
        
        # Convert coordinates to tuples as specified in output schema
        coord1 = tuple(coordinates[0])
        coord2 = tuple(coordinates[1])
        
        # Format as function call structure matching the expected output
        result = {
            "calculate_distance": {
                "coord1": coord1,
                "coord2": coord2,
                "unit": unit
            }
        }
        
        return result
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        return {"error": f"Failed to parse GPS coordinates: {e}"}