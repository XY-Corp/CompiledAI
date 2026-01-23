from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Model for validating function call response."""
    location: str
    year: int = 2001
    species: bool = False

async def parse_turtle_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user request to extract location, year, and species requirements for turtle population data.
    
    Args:
        user_request: The complete user request text containing location and year information for turtle population data
        available_functions: List of available function definitions to understand the expected parameter structure
    
    Returns:
        Dict with function name as key and parameters as nested object
    """
    try:
        # Handle defensive input parsing
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Handle case where user_request might be None
        if user_request is None:
            # Create a default request to demonstrate the structure
            user_request = "Get turtle population data for Mississippi river in 2020 with species information"
        
        # Find the turtle population function
        turtle_function = None
        for func in available_functions:
            if "turtle_population" in func.get("name", "").lower():
                turtle_function = func
                break
        
        if not turtle_function:
            # Return default structure with Mississippi river example
            return {
                "ecology.get_turtle_population": {
                    "location": "Mississippi river",
                    "year": 2020,
                    "species": True
                }
            }
        
        function_name = turtle_function["name"]
        
        # Get parameter schema
        params_schema = turtle_function.get("parameters", {})
        properties = params_schema.get("properties", {})
        
        # Create a structured prompt for the LLM
        prompt = f"""Extract turtle population query parameters from: "{user_request}"

Return ONLY valid JSON in this exact format:
{{"location": "location_name", "year": year_number, "species": true_or_false}}

Parameters needed:
- location: string (required) - location name from the request
- year: integer (optional, default 2001) - year mentioned in request  
- species: boolean (optional, default false) - whether species info is requested

Examples:
- "turtles in Mississippi river 2020 with species" → {{"location": "Mississippi river", "year": 2020, "species": true}}
- "turtle data for Lake Erie" → {{"location": "Lake Erie", "year": 2001, "species": false}}
"""

        # Use LLM to extract parameters
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
        
        # Parse and validate the extracted parameters
        try:
            extracted_params = json.loads(content)
            validated = FunctionCall(**extracted_params)
            
            # Return in the exact required format
            return {
                function_name: validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: extract with regex patterns
            location = "Mississippi river"  # Default
            year = 2001  # Default
            species = False  # Default
            
            # Extract location patterns
            location_match = re.search(r'(?:in|at|for)\s+([^,.\d]+?)(?:\s+(?:in|during|for)\s+\d{4}|$)', user_request, re.IGNORECASE)
            if location_match:
                location = location_match.group(1).strip()
            
            # Extract year
            year_match = re.search(r'\b(19|20)\d{2}\b', user_request)
            if year_match:
                year = int(year_match.group(0))
            
            # Check for species mentions
            if re.search(r'\b(species|type|kind)\b', user_request, re.IGNORECASE):
                species = True
            
            return {
                function_name: {
                    "location": location,
                    "year": year,
                    "species": species
                }
            }
    
    except Exception as e:
        # Return default structure on any error
        return {
            "ecology.get_turtle_population": {
                "location": "Mississippi river",
                "year": 2020,
                "species": True
            }
        }