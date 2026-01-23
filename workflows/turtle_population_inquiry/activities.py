from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class TurtleInquiryResult(BaseModel):
    """Extracted turtle population inquiry parameters."""
    location: str
    year: int = 2001
    species: bool = False


async def parse_turtle_inquiry(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse natural language request about turtle population to extract location, year, and species preference parameters.
    
    Args:
        user_request: The raw natural language user request containing location, year, and species information
        available_functions: List of available function definitions to understand parameter schema
    
    Returns:
        Dict with the function name as key and extracted parameters as nested dict
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Find the turtle population function
        turtle_function = None
        for func in available_functions:
            if "turtle_population" in func.get("name", "").lower():
                turtle_function = func
                break
        
        if not turtle_function:
            return {"error": "No turtle population function found in available functions"}
        
        function_name = turtle_function["name"]
        
        # Create a prompt to extract parameters from the user request
        prompt = f"""Extract turtle population inquiry parameters from this user request: "{user_request}"

Extract:
1. Location (string): The geographic location mentioned (river, lake, state, etc.)
2. Year (integer): Any year mentioned, or use default 2001 if none specified
3. Species (boolean): Whether the user wants species information (true if they mention species/types/kinds, false otherwise)

Return ONLY valid JSON in this exact format:
{{"location": "extracted_location", "year": extracted_year, "species": true_or_false}}

Examples:
- "turtles in Mississippi river in 2020 with species info" → {{"location": "Mississippi river", "year": 2020, "species": true}}
- "turtle count for Colorado river" → {{"location": "Colorado river", "year": 2001, "species": false}}"""
        
        # Use LLM to extract structured data
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Clean up markdown code blocks if present
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate the response
        try:
            extracted_data = json.loads(content)
            validated = TurtleInquiryResult(**extracted_data)
            
            # Return in the exact format specified: function name as key, parameters as nested dict
            return {
                function_name: validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract with regex patterns
            location_match = re.search(r'(?:in|at|for)\s+([^,\n]+?)(?:\s+in\s+\d{4}|\s*$)', user_request, re.IGNORECASE)
            year_match = re.search(r'\b(19|20)\d{2}\b', user_request)
            species_keywords = ['species', 'type', 'kind', 'variety', 'breed']
            
            location = location_match.group(1).strip() if location_match else "unknown location"
            year = int(year_match.group(0)) if year_match else 2001
            species = any(keyword in user_request.lower() for keyword in species_keywords)
            
            return {
                function_name: {
                    "location": location,
                    "year": year,
                    "species": species
                }
            }
            
    except Exception as e:
        return {"error": f"Failed to parse turtle inquiry: {str(e)}"}