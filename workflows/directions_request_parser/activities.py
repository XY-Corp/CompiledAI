from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class DirectionsCall(BaseModel):
    """Structure for parsed directions request."""
    get_directions: Dict[str, Any]


async def parse_directions_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from the user's natural language directions request.
    
    Args:
        user_request: The complete user request text containing the starting location, destination, and any route preferences
        available_functions: List of function definitions providing context about available parameters and their requirements
        
    Returns:
        Dict with 'get_directions' as the key containing extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate we have a user request
        if not user_request or user_request == "None":
            return {
                "get_directions": {
                    "start_location": "<UNKNOWN>",
                    "end_location": "<UNKNOWN>",
                    "route_type": "fastest"
                }
            }
        
        # Find the get_directions function definition
        directions_func = None
        for func in available_functions:
            if func.get('name') == 'get_directions':
                directions_func = func
                break
        
        if not directions_func:
            return {
                "get_directions": {
                    "start_location": "<UNKNOWN>",
                    "end_location": "<UNKNOWN>",
                    "route_type": "fastest"
                }
            }
        
        # Get parameter schema
        params_schema = directions_func.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Create a clear prompt for the LLM
        param_descriptions = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            param_desc = param_info.get('description', '')
            param_descriptions.append(f'"{param_name}" ({param_type}): {param_desc}')
        
        prompt = f"""Extract direction parameters from this user request: "{user_request}"

Available parameters:
{chr(10).join(param_descriptions)}

Extract the locations and route preference. For route_type, use "fastest" unless the user specifically mentions "scenic" or similar preferences.

Return ONLY valid JSON in this exact format:
{{"get_directions": {{"start_location": "extracted_start", "end_location": "extracted_destination", "route_type": "fastest"}}}}"""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
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
            validated = DirectionsCall(**data)
            return validated.model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback - extract using regex patterns
            start_patterns = [
                r'from\s+([^,\n]+?)(?:\s+to|\s*,)',
                r'start(?:ing)?\s+(?:at|from)?\s*:?\s*([^,\n]+?)(?:\s+to|\s*,)',
                r'leaving\s+(?:from)?\s*([^,\n]+?)(?:\s+to|\s*,)',
            ]
            
            end_patterns = [
                r'to\s+([^,\n]+?)(?:\s*[,.]|\s*$)',
                r'destination\s*:?\s*([^,\n]+?)(?:\s*[,.]|\s*$)',
                r'going\s+to\s+([^,\n]+?)(?:\s*[,.]|\s*$)',
            ]
            
            start_location = "<UNKNOWN>"
            end_location = "<UNKNOWN>"
            route_type = "fastest"
            
            # Extract start location
            for pattern in start_patterns:
                match = re.search(pattern, user_request, re.IGNORECASE)
                if match:
                    start_location = match.group(1).strip()
                    break
            
            # Extract end location
            for pattern in end_patterns:
                match = re.search(pattern, user_request, re.IGNORECASE)
                if match:
                    end_location = match.group(1).strip()
                    break
            
            # Check for scenic route preference
            if re.search(r'\b(?:scenic|beautiful|pretty|nice)\b', user_request, re.IGNORECASE):
                route_type = "scenic"
            
            return {
                "get_directions": {
                    "start_location": start_location,
                    "end_location": end_location,
                    "route_type": route_type
                }
            }
            
    except Exception as e:
        # Final fallback with default values
        return {
            "get_directions": {
                "start_location": "<UNKNOWN>",
                "end_location": "<UNKNOWN>",
                "route_type": "fastest"
            }
        }