from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class RouteParams(BaseModel):
    """Define the expected route parameter structure."""
    start_location: str
    end_location: str
    stops: List[str] = []


async def parse_travel_request(
    request_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract travel route information from natural language request and format as function call.
    
    Args:
        request_text: Natural language travel request containing start location, destination, and optional stops
        available_functions: List of available function definitions with their parameters and descriptions
        
    Returns:
        Dict containing route.estimate_time function call with start_location, end_location, and stops
    """
    try:
        # Parse available_functions if it's a JSON string
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate that we have functions
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Find the route.estimate_time function to understand its parameters
        route_function = None
        for func in available_functions:
            if func.get('name') == 'route.estimate_time':
                route_function = func
                break
        
        if not route_function:
            return {"error": "route.estimate_time function not found in available_functions"}
        
        # Create prompt for LLM to extract route information
        prompt = f"""Extract travel route information from this request: "{request_text}"

Please identify:
1. Start location (the departure point/origin city)  
2. End location (the final destination city)
3. Any intermediate stops along the route (cities to visit between start and end)

Return ONLY valid JSON in this exact format:
{{"start_location": "departure city", "end_location": "destination city", "stops": ["intermediate city 1", "intermediate city 2"]}}

If no intermediate stops are mentioned, use an empty array for stops.
Use city names only (e.g. "San Francisco", "Los Angeles", "Santa Barbara").
"""
        
        # Use LLM to extract route information
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated_route = RouteParams(**data)
            
            # Return in the exact format specified: route.estimate_time as key
            return {
                "route.estimate_time": validated_route.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            locations = []
            
            # Common travel patterns
            patterns = [
                r'from\s+([^to]+?)\s+to\s+([^,\.]+)',  # "from X to Y"
                r'([^,]+?)\s+to\s+([^,\.]+)',          # "X to Y"
                r'travel.*?([^,]+?)\s+to\s+([^,\.]+)', # "travel ... X to Y"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, request_text, re.IGNORECASE)
                if match:
                    start_location = match.group(1).strip()
                    end_location = match.group(2).strip()
                    
                    # Look for stops mentioned with words like "via", "through", "stopping at"
                    stops = []
                    stop_patterns = [
                        r'(?:via|through|stopping\s+at|stop\s+in)\s+([^,\.]+)',
                        r'and\s+([^,\.]+?)(?:\s+on\s+the\s+way)',
                    ]
                    
                    for stop_pattern in stop_patterns:
                        stop_matches = re.findall(stop_pattern, request_text, re.IGNORECASE)
                        for stop in stop_matches:
                            clean_stop = stop.strip()
                            if clean_stop and clean_stop not in [start_location, end_location]:
                                stops.append(clean_stop)
                    
                    return {
                        "route.estimate_time": {
                            "start_location": start_location,
                            "end_location": end_location, 
                            "stops": stops
                        }
                    }
            
            # If no patterns match, return error
            return {"error": f"Could not parse travel request: {e}"}
            
    except Exception as e:
        return {"error": f"Failed to process travel request: {str(e)}"}