from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class RestaurantParameters(BaseModel):
    """Structure for restaurant search parameters."""
    cuisine: str = ""
    location: str = ""
    condition: str = ""


async def parse_restaurant_request(
    user_request: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user request to extract restaurant search parameters and format them as a function call.
    
    Args:
        user_request: The complete user request text containing restaurant search criteria
        function_schema: The get_restaurant function definition with parameters structure
        
    Returns:
        Function call structure with get_restaurant as the key and extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # Validate function_schema structure
        if not isinstance(function_schema, (dict, list)):
            return {"error": f"function_schema must be dict or list, got {type(function_schema).__name__}"}
        
        # Handle list format (multiple functions) - find get_restaurant
        if isinstance(function_schema, list):
            get_restaurant_func = None
            for func in function_schema:
                if func.get('name') == 'get_restaurant':
                    get_restaurant_func = func
                    break
            
            if not get_restaurant_func:
                return {"error": "get_restaurant function not found in function_schema"}
            
            function_schema = get_restaurant_func
        
        # Get parameter details for context
        params_schema = function_schema.get('parameters', {})
        
        # Create prompt for LLM to extract restaurant parameters
        prompt = f"""Extract restaurant search parameters from this user request: "{user_request}"

The get_restaurant function expects these parameters:
- cuisine: type of food/cuisine
- location: city, area, or address
- condition: special requirements (hours, features, etc.)

Extract the values from the user request and return ONLY valid JSON in this exact format:
{{"cuisine": "extracted_cuisine", "location": "extracted_location", "condition": "extracted_condition"}}

If a parameter is not mentioned in the request, use an empty string "".

User request: {user_request}"""

        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
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
            validated = RestaurantParameters(**data)
            extracted_params = validated.model_dump()
            
            # Return in the required format: {"get_restaurant": {...}}
            return {
                "get_restaurant": extracted_params
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            cuisine_match = re.search(r'(?:cuisine|food|type).*?([a-zA-Z]+(?:\s+[a-zA-Z]+)*)', user_request.lower())
            location_match = re.search(r'(?:in|at|near|location).*?([a-zA-Z]+(?:\s+[a-zA-Z]+)*)', user_request.lower())
            condition_match = re.search(r'(?:that|which|open|close|deliver|condition).*?([^.]*)', user_request.lower())
            
            fallback_params = {
                "cuisine": cuisine_match.group(1).strip() if cuisine_match else "",
                "location": location_match.group(1).strip() if location_match else "",
                "condition": condition_match.group(1).strip() if condition_match else ""
            }
            
            return {
                "get_restaurant": fallback_params
            }
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in function_schema: {e}"}
    except KeyError as e:
        return {"error": f"Missing field in function_schema: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}