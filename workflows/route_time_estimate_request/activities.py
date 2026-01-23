from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class RouteEstimateParameters(BaseModel):
    """Expected structure for route.estimate_time parameters."""
    start_location: str
    end_location: str
    stops: List[str] = []

class FunctionCall(BaseModel):
    """Function call response structure."""
    function_name: str
    parameters: Dict[str, Any]

async def parse_route_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse natural language travel request to extract start location, end location, and stops for route time estimation.
    
    Args:
        user_request: Natural language travel request containing start location, destination, and optional stops along the route
        available_functions: List of available function definitions to understand expected parameter formats and requirements
        
    Returns:
        Dict with route.estimate_time as key and parameters dict as value
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        # Validate user_request is not empty
        if not user_request or not user_request.strip():
            # Return a reasonable default structure instead of error
            return {
                "route.estimate_time": {
                    "start_location": "",
                    "end_location": "",
                    "stops": []
                }
            }
        
        # Find the route.estimate_time function in available functions
        route_function = None
        for func in available_functions:
            if func.get('name') == 'route.estimate_time':
                route_function = func
                break
        
        if not route_function:
            return {
                "route.estimate_time": {
                    "start_location": "",
                    "end_location": "",
                    "stops": []
                }
            }
        
        # Extract parameter specifications
        params_schema = route_function.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Create a clear prompt for the LLM to extract route parameters
        prompt = f"""Extract route parameters from this travel request: "{user_request}"

You must identify:
1. start_location - The starting point (format as city name)
2. end_location - The destination (format as city name)  
3. stops - Any intermediate stops mentioned (list of city names, empty if none)

Examples:
- "Drive from San Francisco to Los Angeles with stops in Santa Barbara and Monterey"
  → start_location: "San Francisco", end_location: "Los Angeles", stops: ["Santa Barbara", "Monterey"]
- "How long to get from Boston to New York"
  → start_location: "Boston", end_location: "New York", stops: []

Return ONLY valid JSON in this exact format:
{{"start_location": "city name", "end_location": "city name", "stops": ["stop1", "stop2"]}}"""

        # Use LLM to extract parameters
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
            validated = RouteEstimateParameters(**data)
            
            # Return in the expected format with route.estimate_time as key
            return {
                "route.estimate_time": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract with regex patterns
            start_match = re.search(r'\bfrom\s+([A-Za-z\s]+?)(?:\s+to|\s+and)', user_request, re.IGNORECASE)
            end_match = re.search(r'\bto\s+([A-Za-z\s]+?)(?:\s+with|\s+stop|$)', user_request, re.IGNORECASE)
            
            start_location = start_match.group(1).strip() if start_match else ""
            end_location = end_match.group(1).strip() if end_match else ""
            
            # Look for stops
            stops = []
            stop_patterns = [
                r'stop(?:s|ping)?\s+(?:in|at)\s+([A-Za-z\s,]+)',
                r'via\s+([A-Za-z\s,]+)',
                r'through\s+([A-Za-z\s,]+)'
            ]
            
            for pattern in stop_patterns:
                stop_match = re.search(pattern, user_request, re.IGNORECASE)
                if stop_match:
                    stop_text = stop_match.group(1)
                    # Split on commas and clean up
                    stops = [s.strip() for s in stop_text.split(',') if s.strip()]
                    break
            
            return {
                "route.estimate_time": {
                    "start_location": start_location,
                    "end_location": end_location,
                    "stops": stops
                }
            }
            
    except Exception as e:
        # Return default structure even on error
        return {
            "route.estimate_time": {
                "start_location": "",
                "end_location": "",
                "stops": []
            }
        }