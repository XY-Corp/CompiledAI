from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Expected function call structure."""
    start_location: str
    end_location: str
    units: str = "miles"


async def parse_distance_query(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract location information from user query and format as function call for geo_distance.calculate.
    
    Args:
        query_text: The user's natural language query containing location names and distance request
        available_functions: List of available function definitions for context and validation
        
    Returns:
        Dict with function call structure: {"geo_distance.calculate": {"start_location": "...", "end_location": "...", "units": "..."}}
    """
    try:
        # Parse JSON string input if needed
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate types
        if not isinstance(available_functions, list):
            return {"geo_distance.calculate": {"error": "available_functions must be a list"}}
        
        # Find the geo_distance.calculate function to get parameter details
        geo_function = None
        for func in available_functions:
            if func.get('name') == 'geo_distance.calculate':
                geo_function = func
                break
        
        if not geo_function:
            return {"geo_distance.calculate": {"error": "geo_distance.calculate function not found"}}
        
        # Get parameters schema
        params_schema = geo_function.get('parameters', {})
        
        # Format function information for LLM
        functions_text = f"Function: {geo_function['name']}\n"
        functions_text += f"Description: {geo_function.get('description', '')}\n"
        functions_text += "Parameters:\n"
        
        for param_name, param_info in params_schema.items():
            if isinstance(param_info, dict):
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '')
            else:
                param_type = str(param_info)
                param_desc = ''
            functions_text += f"  - {param_name}: {param_type} - {param_desc}\n"
        
        # Create prompt for LLM to extract location information
        prompt = f"""User query: "{query_text}"

{functions_text}

Extract the location information from the user's query and format it for the geo_distance.calculate function.

CRITICAL REQUIREMENTS:
- Use EXACT parameter names from the function schema above
- Extract two locations (start and end) from the query
- Determine appropriate units (miles, kilometers, etc.) or default to "miles"
- Locations should be in a clear format like "City, State" or "City, Country"

Return ONLY valid JSON in this exact format:
{{"start_location": "Location1", "end_location": "Location2", "units": "miles"}}"""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
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
            validated = FunctionCall(**data)
            
            # Return in the exact format specified by output schema
            return {
                "geo_distance.calculate": validated.model_dump()
            }
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract locations using regex patterns
            locations = []
            
            # Common patterns for locations
            city_state_pattern = r'\b([A-Z][a-zA-Z\s]+),\s*([A-Z]{2})\b'
            city_country_pattern = r'\b([A-Z][a-zA-Z\s]+),\s*([A-Z][a-zA-Z\s]+)\b'
            
            # Find city, state patterns first
            matches = re.findall(city_state_pattern, query_text)
            for city, state in matches:
                locations.append(f"{city.strip()}, {state}")
            
            # If not enough locations, try city, country pattern
            if len(locations) < 2:
                matches = re.findall(city_country_pattern, query_text)
                for city, country in matches:
                    if f"{city.strip()}, {country.strip()}" not in locations:
                        locations.append(f"{city.strip()}, {country.strip()}")
            
            # Extract units
            units = "miles"  # default
            if re.search(r'\bkilometer[s]?\b|\bkm\b', query_text.lower()):
                units = "kilometers"
            elif re.search(r'\bmile[s]?\b|\bmi\b', query_text.lower()):
                units = "miles"
            
            if len(locations) >= 2:
                return {
                    "geo_distance.calculate": {
                        "start_location": locations[0],
                        "end_location": locations[1],
                        "units": units
                    }
                }
            else:
                return {
                    "geo_distance.calculate": {
                        "error": f"Could not extract two locations from query. Found: {locations}"
                    }
                }
                
    except Exception as e:
        return {
            "geo_distance.calculate": {
                "error": f"Failed to parse query: {str(e)}"
            }
        }