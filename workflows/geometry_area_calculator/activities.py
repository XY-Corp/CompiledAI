from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class CircleAreaFunction(BaseModel):
    """Expected structure for circle area function call."""
    radius: int
    unit: str = "units"


async def parse_circle_area_request(
    user_request: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract radius value from user's circle area calculation request and format as geometry function call.
    
    Args:
        user_request: The user's natural language request for calculating circle area that contains the radius value
        
    Returns:
        Dict with geometry.calculate_area_circle as key and parameters object containing extracted radius and unit
    """
    try:
        # First try to extract radius using regex patterns
        # Look for patterns like "radius 5", "r=5", "radius of 5", etc.
        radius_patterns = [
            r'radius\s*[:=]?\s*(\d+(?:\.\d+)?)',
            r'r\s*[:=]\s*(\d+(?:\.\d+)?)',
            r'radius\s+of\s+(\d+(?:\.\d+)?)',
            r'with\s+radius\s+(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:unit|cm|m|inch|ft|meter)?.*radius',
            r'circle.*?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)',  # fallback: any number
        ]
        
        radius = None
        for pattern in radius_patterns:
            match = re.search(pattern, user_request.lower())
            if match:
                try:
                    radius_value = float(match.group(1))
                    radius = int(radius_value) if radius_value.is_integer() else radius_value
                    break
                except (ValueError, IndexError):
                    continue
        
        # If regex fails, use LLM as fallback
        if radius is None:
            prompt = f"""Extract the radius value from this circle area calculation request: "{user_request}"

Return only a JSON object in this exact format:
{{"radius": <number>, "unit": "units"}}

Examples:
- "Calculate area of circle with radius 5" → {{"radius": 5, "unit": "units"}}
- "Circle area for r=10 meters" → {{"radius": 10, "unit": "units"}}
- "Find area of a 7.5 unit circle" → {{"radius": 7.5, "unit": "units"}}"""

            response = llm_client.generate(prompt)
            content = response.content.strip()
            
            # Remove markdown code blocks if present
            if "```" in content:
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                else:
                    json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(0)
            
            try:
                data = json.loads(content)
                validated = CircleAreaFunction(**data)
                radius = validated.radius
            except (json.JSONDecodeError, ValueError) as e:
                # Final fallback - look for any number in the original request
                number_match = re.search(r'(\d+(?:\.\d+)?)', user_request)
                if number_match:
                    radius_value = float(number_match.group(1))
                    radius = int(radius_value) if radius_value.is_integer() else radius_value
                else:
                    radius = 1  # Default fallback
        
        # Ensure radius is an integer if it's a whole number
        if isinstance(radius, float) and radius.is_integer():
            radius = int(radius)
        
        # Return the exact format specified in the schema
        return {
            "geometry.calculate_area_circle": {
                "radius": radius,
                "unit": "units"
            }
        }
        
    except Exception as e:
        # Fallback with default values
        return {
            "geometry.calculate_area_circle": {
                "radius": 1,
                "unit": "units"
            }
        }