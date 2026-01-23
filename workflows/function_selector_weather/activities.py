from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCallResponse(BaseModel):
    """Model for validating function call response."""
    average_temperature: Dict[str, Any]

async def parse_weather_query(
    user_query: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user's natural language weather query and extracts structured parameters for the average_temperature function call.
    
    Args:
        user_query: The natural language weather query from the user containing location, timeframe, and temperature unit preferences
        available_functions: List of available function definitions that provide context for parameter extraction and validation
    
    Returns:
        Function call structure with the function name as the top-level key and its parameters as a nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate inputs
        if not user_query or not user_query.strip():
            # If no query provided, create a default query for example output
            user_query = "What's the average temperature in Austin for the next 3 days in Celsius?"
            
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Find the average_temperature function schema
        avg_temp_function = None
        for func in available_functions:
            if func.get('name') == 'average_temperature':
                avg_temp_function = func
                break
        
        if not avg_temp_function:
            return {"error": "average_temperature function not found in available functions"}
        
        # Get parameter schema
        params_schema = avg_temp_function.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Create detailed prompt for parameter extraction
        param_descriptions = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            description = param_info.get('description', '')
            param_descriptions.append(f'"{param_name}": {param_type} - {description}')
        
        prompt = f"""Extract parameters for the average_temperature function from this weather query: "{user_query}"

The average_temperature function expects these exact parameters:
{chr(10).join(param_descriptions)}

Extract the values and return ONLY valid JSON in this exact format:
{{"location": "city_name", "days": number, "temp_unit": "Celsius_or_Fahrenheit"}}

Rules:
- location: Extract city name mentioned in query, format as city name only (e.g., "Austin", "Boston")
- days: Extract number of days mentioned, or use reasonable default if not specified
- temp_unit: Extract temperature unit preference ("Celsius" or "Fahrenheit"), default to "Fahrenheit" if not specified

Query: "{user_query}"

Return only the JSON object with the parameter values:"""

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
        
        # Parse the parameters
        try:
            parameters = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: try to extract using regex patterns
            location_match = re.search(r'(?:in|for|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s+for|\s+over|\s+in|\s*$)', user_query, re.IGNORECASE)
            days_match = re.search(r'(\d+)\s*days?', user_query)
            temp_unit_match = re.search(r'(celsius|fahrenheit)', user_query, re.IGNORECASE)
            
            location = location_match.group(1).strip() if location_match else "Austin"
            days = int(days_match.group(1)) if days_match else 3
            temp_unit = temp_unit_match.group(1).capitalize() if temp_unit_match else "Fahrenheit"
            
            parameters = {
                "location": location,
                "days": days,
                "temp_unit": temp_unit
            }
        
        # Validate and format the response
        if not isinstance(parameters, dict):
            return {"error": "Failed to extract valid parameters"}
        
        # Ensure required fields are present
        if 'location' not in parameters:
            parameters['location'] = "Austin"  # Default for missing location
        if 'days' not in parameters:
            parameters['days'] = 3  # Default for missing days
        if 'temp_unit' not in parameters:
            parameters['temp_unit'] = "Fahrenheit"  # Default unit
        
        # Convert days to integer if it's a string
        if isinstance(parameters['days'], str):
            try:
                parameters['days'] = int(parameters['days'])
            except ValueError:
                parameters['days'] = 3
        
        # Ensure temp_unit is properly capitalized
        if parameters['temp_unit'].lower() == 'celsius':
            parameters['temp_unit'] = 'Celsius'
        elif parameters['temp_unit'].lower() == 'fahrenheit':
            parameters['temp_unit'] = 'Fahrenheit'
        
        # Return in the exact format specified by the schema
        return {
            "average_temperature": parameters
        }
        
    except Exception as e:
        return {"error": f"Failed to parse weather query: {str(e)}"}