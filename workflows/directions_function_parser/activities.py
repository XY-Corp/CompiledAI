from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class DirectionsParameters(BaseModel):
    """Expected structure for get_directions function parameters."""
    start_location: str
    end_location: str
    route_type: str = "fastest"


async def extract_directions_parameters(
    user_request: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user's directions request and extract function call parameters for get_directions.
    
    Args:
        user_request: The raw user input requesting directions that needs to be parsed for location and route preferences
        function_schema: The get_directions function definition containing parameter types and descriptions for reference
        
    Returns:
        Dict with 'get_directions' as the key containing extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # If function_schema is actually a list of functions, find get_directions
        if isinstance(function_schema, list):
            directions_func = None
            for func in function_schema:
                if func.get('name') == 'get_directions':
                    directions_func = func
                    break
            if directions_func:
                function_schema = directions_func
        
        # Validate we have a user request
        if not user_request or user_request == "None":
            return {
                "get_directions": {
                    "start_location": "<UNKNOWN>",
                    "end_location": "<UNKNOWN>",
                    "route_type": "fastest"
                }
            }
        
        # Get parameter schema for reference
        params_schema = function_schema.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Build parameter descriptions for LLM context
        param_descriptions = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            param_desc = param_info.get('description', '')
            param_descriptions.append(f'"{param_name}" ({param_type}): {param_desc}')
        
        # Create a clear prompt for the LLM to extract parameters
        prompt = f"""Extract direction parameters from this user request: "{user_request}"

The get_directions function expects these parameters:
{chr(10).join(param_descriptions)}

Common route types: "fastest", "shortest", "scenic", "avoid_tolls"

Return ONLY valid JSON in this exact format:
{{"start_location": "extracted_start", "end_location": "extracted_destination", "route_type": "fastest"}}

If any location is unclear, use "<UNKNOWN>". Default route_type to "fastest" if not specified."""

        # Use LLM to extract parameters from natural language
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
            validated = DirectionsParameters(**data)
            
            return {
                "get_directions": validated.model_dump()
            }
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract locations with regex patterns
            start_patterns = [
                r'(?:from|start|starting|begin|departure|origin)[\s:]+([^,\n]+?)(?:\s+to|\s+destination|\s*,|$)',
                r'^([^,\n]+?)\s+to\s+',
                r'directions from\s+([^,\n]+?)(?:\s+to|$)'
            ]
            
            end_patterns = [
                r'(?:to|destination|end|ending|arrive|arrival)[\s:]+([^,\n]+?)(?:\s*,|$)',
                r'\s+to\s+([^,\n]+?)(?:\s*,|$)',
                r'directions.*?to\s+([^,\n]+?)(?:\s*,|$)'
            ]
            
            start_location = "<UNKNOWN>"
            end_location = "<UNKNOWN>"
            
            # Try to extract start location
            for pattern in start_patterns:
                match = re.search(pattern, user_request, re.IGNORECASE)
                if match:
                    start_location = match.group(1).strip()
                    break
            
            # Try to extract end location
            for pattern in end_patterns:
                match = re.search(pattern, user_request, re.IGNORECASE)
                if match:
                    end_location = match.group(1).strip()
                    break
            
            # Check for route type preferences
            route_type = "fastest"
            if re.search(r'\b(shortest|short|quick)\b', user_request, re.IGNORECASE):
                route_type = "shortest"
            elif re.search(r'\b(scenic|beautiful|pretty)\b', user_request, re.IGNORECASE):
                route_type = "scenic"
            elif re.search(r'\b(avoid.?toll|no.?toll|toll.?free)\b', user_request, re.IGNORECASE):
                route_type = "avoid_tolls"
            
            return {
                "get_directions": {
                    "start_location": start_location,
                    "end_location": end_location,
                    "route_type": route_type
                }
            }
            
    except Exception as e:
        # Ultimate fallback
        return {
            "get_directions": {
                "start_location": "<UNKNOWN>",
                "end_location": "<UNKNOWN>",
                "route_type": "fastest"
            }
        }