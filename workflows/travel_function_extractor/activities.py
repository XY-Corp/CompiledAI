from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class TravelItineraryParams(BaseModel):
    """Expected structure for travel itinerary generator parameters."""
    destination: str
    days: int
    daily_budget: int
    exploration_type: Optional[str] = "urban"

class FunctionCallResult(BaseModel):
    """Function call structure."""
    travel_itinerary_generator: TravelItineraryParams

async def extract_travel_parameters(
    travel_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts travel itinerary parameters from natural language request and formats as function call structure."""
    
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Find the travel_itinerary_generator function
        travel_function = None
        for func in available_functions:
            if func.get('name') == 'travel_itinerary_generator':
                travel_function = func
                break
        
        if not travel_function:
            return {"error": "travel_itinerary_generator function not found"}
        
        # Get parameter schema
        params_schema = travel_function.get('parameters', {}).get('properties', {})
        
        # Create LLM prompt to extract parameters
        prompt = f"""Extract travel itinerary parameters from this request: "{travel_request}"

You must extract these exact parameters:
- destination: The destination city/location (required)
- days: Number of days for the trip as integer (required)  
- daily_budget: Maximum daily budget as integer (required)
- exploration_type: One of "nature", "urban", "history", "culture" (optional, default "urban")

Return ONLY valid JSON in this exact format:
{{"destination": "city_name", "days": number, "daily_budget": number, "exploration_type": "type"}}

Examples:
- "I want to visit Tokyo for 7 days with $100 per day budget for nature exploration" 
  → {{"destination": "Tokyo", "days": 7, "daily_budget": 100, "exploration_type": "nature"}}
- "Plan a 5-day Paris trip, $150 daily budget" 
  → {{"destination": "Paris", "days": 5, "daily_budget": 150, "exploration_type": "urban"}}"""

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
            params_data = json.loads(content)
            validated_params = TravelItineraryParams(**params_data)
            
            # Return in the exact format required by the schema
            result = {
                "travel_itinerary_generator": validated_params.model_dump()
            }
            
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract with regex patterns
            destination_match = re.search(r'(?:to|visit)\s+([A-Za-z\s]+?)(?:\s+for|\s+with|$)', travel_request, re.IGNORECASE)
            days_match = re.search(r'(\d+)\s*days?', travel_request, re.IGNORECASE)
            budget_match = re.search(r'\$?(\d+).*(?:per\s+day|daily|budget)', travel_request, re.IGNORECASE)
            
            destination = destination_match.group(1).strip() if destination_match else "Unknown"
            days = int(days_match.group(1)) if days_match else 7
            daily_budget = int(budget_match.group(1)) if budget_match else 100
            
            # Detect exploration type
            exploration_type = "urban"  # default
            if re.search(r'nature|outdoor|hiking|park', travel_request, re.IGNORECASE):
                exploration_type = "nature"
            elif re.search(r'history|historical|museum', travel_request, re.IGNORECASE):
                exploration_type = "history"  
            elif re.search(r'culture|cultural|art|food', travel_request, re.IGNORECASE):
                exploration_type = "culture"
            
            return {
                "travel_itinerary_generator": {
                    "destination": destination,
                    "days": days,
                    "daily_budget": daily_budget,
                    "exploration_type": exploration_type
                }
            }
            
    except Exception as e:
        return {"error": f"Failed to extract travel parameters: {str(e)}"}