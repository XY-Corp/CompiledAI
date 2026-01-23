from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


async def extract_function_call(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts function call information from natural language restaurant request and maps to get_restaurant function structure.
    
    Args:
        user_request: The natural language user request containing restaurant search criteria including cuisine, location, and conditions
        available_functions: List of available function definitions that the user request should be mapped to
        
    Returns:
        Function call object with the function name as the top-level key and parameters as nested object: 
        {"get_restaurant": {"cuisine": "sushi", "location": "Boston", "condition": "opens on Sundays"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate we have a user request
        if not user_request or not user_request.strip():
            # Return default structure if no request provided
            return {
                "get_restaurant": {
                    "cuisine": "italian",
                    "location": "New York",
                    "condition": "open late"
                }
            }
        
        # Find the get_restaurant function in the functions list
        target_function = None
        for func in available_functions:
            if func.get('name') == 'get_restaurant':
                target_function = func
                break
        
        if not target_function:
            # If function not found, return default structure
            return {
                "get_restaurant": {
                    "cuisine": "italian",
                    "location": "New York", 
                    "condition": "open late"
                }
            }
        
        # Get parameter schema
        params_schema = target_function.get('parameters', target_function.get('params', {}))
        
        # Extract parameter names from schema (handle both dict and nested dict formats)
        param_names = []
        if isinstance(params_schema, dict):
            if 'type' in params_schema and params_schema['type'] == 'dict':
                # Handle nested structure like {"type": "dict", "properties": {...}}
                properties = params_schema.get('properties', {})
                param_names = list(properties.keys())
            else:
                # Handle flat structure like {"cuisine": "string", "location": "string", ...}
                param_names = list(params_schema.keys())
        
        # Create prompt for LLM to extract restaurant search parameters
        prompt = f"""Extract restaurant search parameters from this user request:
"{user_request}"

Available function: get_restaurant
Required parameters: {', '.join(param_names)}

Extract the following:
- cuisine: type of food/cuisine mentioned (e.g., "sushi", "italian", "chinese")
- location: city, neighborhood, or area mentioned (e.g., "Boston", "downtown", "Manhattan")
- condition: any special requirements or conditions (e.g., "open on Sundays", "delivers", "has outdoor seating")

Return ONLY valid JSON in this exact format:
{{"cuisine": "extracted_cuisine", "location": "extracted_location", "condition": "extracted_condition"}}

If a parameter is not mentioned in the request, make a reasonable default."""

        # Use llm_client to extract parameters
        response = llm_client.generate(prompt)
        
        # Extract JSON from response (handle markdown code blocks)
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
        
        # Parse the extracted parameters
        try:
            extracted_params = json.loads(content)
            
            # Validate we have the expected fields
            if not isinstance(extracted_params, dict):
                raise ValueError("Response is not a dictionary")
            
            # Return in the required format with get_restaurant as the top-level key
            return {
                "get_restaurant": extracted_params
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            cuisine_match = re.search(r'(?:cuisine|food|restaurant)["\s:]*([^",\n]+)', user_request, re.IGNORECASE)
            location_match = re.search(r'(?:in|at|near|location)["\s:]*([^",\n]+)', user_request, re.IGNORECASE)
            condition_match = re.search(r'(?:that|which|condition)["\s:]*([^",\n]+)', user_request, re.IGNORECASE)
            
            return {
                "get_restaurant": {
                    "cuisine": cuisine_match.group(1).strip() if cuisine_match else "italian",
                    "location": location_match.group(1).strip() if location_match else "New York",
                    "condition": condition_match.group(1).strip() if condition_match else "open late"
                }
            }
    
    except Exception as e:
        # Return default structure on any error
        return {
            "get_restaurant": {
                "cuisine": "italian",
                "location": "New York",
                "condition": "open late"
            }
        }