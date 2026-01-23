from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

async def parse_driving_distance_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes natural language text to extract origin and destination locations for driving distance calculation, then formats the response as a function call.
    
    Args:
        user_request: The complete natural language request from the user asking for driving distance between locations
        available_functions: List of available function definitions to understand the expected parameter format
        
    Returns:
        Dict with function name as key and parameters containing origin, destination, and optional unit
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate we have a user request
        if not user_request or user_request == "None":
            return {
                "get_shortest_driving_distance": {
                    "origin": "<UNKNOWN>",
                    "destination": "<UNKNOWN>",
                    "unit": "km"
                }
            }
        
        # Find the get_shortest_driving_distance function definition
        distance_func = None
        for func in available_functions:
            if func.get('name') == 'get_shortest_driving_distance':
                distance_func = func
                break
        
        if not distance_func:
            return {
                "get_shortest_driving_distance": {
                    "origin": "<UNKNOWN>",
                    "destination": "<UNKNOWN>",
                    "unit": "km"
                }
            }
        
        # Get parameter schema
        params_schema = distance_func.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Create a clear prompt for the LLM
        param_descriptions = []
        for param_name, param_info in properties.items():
            if isinstance(param_info, dict):
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '')
                param_descriptions.append(f'"{param_name}" ({param_type}): {param_desc}')
            else:
                param_descriptions.append(f'"{param_name}": {param_info}')
        
        prompt = f"""Extract driving distance parameters from this user request: "{user_request}"

Available function: get_shortest_driving_distance
Required parameters:
{chr(10).join(param_descriptions)}

CRITICAL: Use these EXACT parameter names:
- "origin" for the starting location
- "destination" for the ending location  
- "unit" for distance measurement (optional, defaults to "km")

Examples:
- "How far is it from New York to Boston?" → origin: "New York", destination: "Boston", unit: "km"
- "Distance between LA and San Francisco in miles" → origin: "LA", destination: "San Francisco", unit: "miles"
- "Driving distance from Chicago to Detroit" → origin: "Chicago", destination: "Detroit", unit: "km"

Return ONLY valid JSON in this format:
{{"origin": "starting_location", "destination": "ending_location", "unit": "km_or_miles"}}"""
        
        response = llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
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
        class DrivingDistanceParams(BaseModel):
            origin: str
            destination: str
            unit: str = "km"
        
        try:
            data = json.loads(content)
            validated = DrivingDistanceParams(**data)
            
            # Return in the exact format specified by the schema
            return {
                "get_shortest_driving_distance": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract locations with regex patterns
            origin = "<UNKNOWN>"
            destination = "<UNKNOWN>"
            unit = "km"
            
            # Common patterns for location extraction
            patterns = [
                r'from\s+(.+?)\s+to\s+(.+?)(?:\s|$)',
                r'between\s+(.+?)\s+and\s+(.+?)(?:\s|$)',
                r'(.+?)\s+to\s+(.+?)(?:\s|$)',
                r'distance.*?(.+?)\s+(.+?)(?:\s|$)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, user_request.lower())
                if match:
                    origin = match.group(1).strip()
                    destination = match.group(2).strip()
                    break
            
            # Check for unit preferences
            if "mile" in user_request.lower():
                unit = "miles"
            elif "km" in user_request.lower() or "kilometer" in user_request.lower():
                unit = "km"
                
            return {
                "get_shortest_driving_distance": {
                    "origin": origin,
                    "destination": destination,
                    "unit": unit
                }
            }
            
    except Exception as e:
        return {
            "get_shortest_driving_distance": {
                "origin": "<UNKNOWN>",
                "destination": "<UNKNOWN>",
                "unit": "km"
            }
        }