from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

async def extract_routing_parameters(
    user_request: str,
    function_schema: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user routing request to extract start location, end location, and toll road preferences for the map_routing.fastest_route function call.
    
    Args:
        user_request: The raw user input text containing routing request with locations and preferences
        function_schema: Available function definitions providing parameter structure and validation context
        
    Returns:
        Dict with map_routing.fastest_route as key and extracted parameters as nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # Validate function_schema is a list
        if not isinstance(function_schema, list):
            return {"map_routing.fastest_route": {"start_location": "", "end_location": "", "avoid_tolls": False}}
        
        # Define the expected output structure
        class RouteParameters(BaseModel):
            start_location: str
            end_location: str
            avoid_tolls: bool = False
        
        # If user_request is empty or None, return default structure
        if not user_request:
            return {
                "map_routing.fastest_route": {
                    "start_location": "",
                    "end_location": "",
                    "avoid_tolls": False
                }
            }
        
        # Create a clean prompt for LLM to extract routing information
        prompt = f"""Extract routing parameters from this user request: "{user_request}"

Return ONLY valid JSON in this exact format:
{{"start_location": "departure location", "end_location": "destination location", "avoid_tolls": true}}

Requirements:
- start_location: Extract the departure/from location as a string
- end_location: Extract the destination/to location as a string  
- avoid_tolls: Set to true if user wants to avoid tolls/toll roads, false otherwise

Examples:
"Route from San Francisco to Los Angeles avoiding tolls" → {{"start_location": "San Francisco", "end_location": "Los Angeles", "avoid_tolls": true}}
"Fastest route from NYC to Boston" → {{"start_location": "NYC", "end_location": "Boston", "avoid_tolls": false}}"""

        response = llm_client.generate(prompt)
        content = response.content.strip()

        # Remove markdown code blocks if present
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)

        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = RouteParameters(**data)
            
            # Return in the required format with map_routing.fastest_route as key
            return {
                "map_routing.fastest_route": validated.model_dump()
            }
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract locations using regex patterns
            start_location = ""
            end_location = ""
            avoid_tolls = False
            
            # Look for "from X to Y" patterns
            from_to_match = re.search(r'from\s+([^,\s]+(?:\s+[^,\s]+)*)\s+to\s+([^,\s]+(?:\s+[^,\s]+)*)', user_request, re.IGNORECASE)
            if from_to_match:
                start_location = from_to_match.group(1).strip()
                end_location = from_to_match.group(2).strip()
            
            # Check for toll avoidance keywords
            if re.search(r'\b(avoid|no|without)\s+toll', user_request, re.IGNORECASE):
                avoid_tolls = True
            
            return {
                "map_routing.fastest_route": {
                    "start_location": start_location,
                    "end_location": end_location,
                    "avoid_tolls": avoid_tolls
                }
            }
            
    except Exception as e:
        # Return error structure in the expected format
        return {
            "map_routing.fastest_route": {
                "start_location": "",
                "end_location": "",
                "avoid_tolls": False
            }
        }