from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class TravelParameters(BaseModel):
    """Define the expected travel itinerary parameters."""
    destination: str
    days: int
    daily_budget: int
    exploration_type: str = "urban"

async def parse_travel_request(
    request_text: str,
    function_schema: dict | list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract travel function parameters from natural language request using LLM analysis.
    
    Args:
        request_text: The complete natural language travel request containing destination, duration, budget, and preferences
        function_schema: The function definition schema containing parameter specifications and validation rules
        
    Returns:
        Dict with travel_itinerary_generator containing extracted parameters
    """
    try:
        # Parse function_schema if it's a JSON string
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # Handle case where function_schema is a list (find travel_itinerary_generator)
        travel_function = None
        if isinstance(function_schema, list):
            for func in function_schema:
                if func.get('name') == 'travel_itinerary_generator':
                    travel_function = func
                    break
        elif isinstance(function_schema, dict):
            if function_schema.get('name') == 'travel_itinerary_generator':
                travel_function = function_schema
        
        if not travel_function:
            return {"error": "travel_itinerary_generator function not found in schema"}
        
        # Extract parameter specifications
        params_schema = travel_function.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Create a clear prompt for the LLM to extract travel parameters
        prompt = f"""Extract travel itinerary parameters from this request: "{request_text}"

Based on the function schema, extract these parameters:
- destination: The destination city (string)
- days: Number of days for the trip (integer)
- daily_budget: Maximum daily budget (integer)
- exploration_type: Type of exploration - must be one of: nature, urban, history, culture (default: urban)

Return ONLY valid JSON in this exact format:
{{"destination": "city_name", "days": number, "daily_budget": number, "exploration_type": "type"}}

If any required information is missing from the request, make reasonable assumptions based on context."""

        # Use LLM client to extract parameters
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
        
        # Parse and validate the extracted parameters
        try:
            extracted_data = json.loads(content)
            
            # Validate with Pydantic model
            validated_params = TravelParameters(**extracted_data)
            
            # Return in the expected format
            return {
                "travel_itinerary_generator": validated_params.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract basic info with regex patterns
            destination_match = re.search(r'(?:to|visit|go to|travel to)\s+([A-Za-z\s]+?)(?:\s|,|$)', request_text, re.IGNORECASE)
            days_match = re.search(r'(\d+)\s*(?:days?|nights?)', request_text, re.IGNORECASE)
            budget_match = re.search(r'(\d+)\s*(?:dollars?|\$|budget)', request_text, re.IGNORECASE)
            
            destination = destination_match.group(1).strip() if destination_match else "Tokyo"
            days = int(days_match.group(1)) if days_match else 7
            budget = int(budget_match.group(1)) if budget_match else 100
            
            # Determine exploration type based on keywords
            exploration_type = "urban"  # default
            if re.search(r'nature|hiking|outdoor|mountains|beach', request_text, re.IGNORECASE):
                exploration_type = "nature"
            elif re.search(r'history|historical|museums?|monuments?', request_text, re.IGNORECASE):
                exploration_type = "history"
            elif re.search(r'culture|cultural|art|local|traditional', request_text, re.IGNORECASE):
                exploration_type = "culture"
            
            return {
                "travel_itinerary_generator": {
                    "destination": destination,
                    "days": days,
                    "daily_budget": budget,
                    "exploration_type": exploration_type
                }
            }
            
    except Exception as e:
        return {"error": f"Failed to parse travel request: {str(e)}"}