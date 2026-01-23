from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class ForestGrowthParameters(BaseModel):
    """Pydantic model for forest growth forecast parameters."""
    location: str
    years: int
    include_human_impact: bool

async def parse_forest_growth_request(
    user_query: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user's natural language query about forest growth prediction and extracts the specific parameters needed for the forest_growth_forecast function call.
    
    Args:
        user_query: The natural language user request about forest growth prediction containing location, time period, and impact considerations
        available_functions: List of available function definitions with their parameters and descriptions to guide parameter extraction
        
    Returns:
        Dict with forest_growth_forecast as key containing location, years, and include_human_impact parameters
    """
    try:
        # Parse available_functions if it's a JSON string
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        # Find the forest_growth_forecast function schema
        forecast_function = None
        for func in available_functions:
            if func.get('name') == 'forest_growth_forecast':
                forecast_function = func
                break
                
        if not forecast_function:
            # If function not found, return a default structure
            return {
                "forest_growth_forecast": {
                    "location": "<UNKNOWN>",
                    "years": 5,
                    "include_human_impact": True
                }
            }
            
        # Get parameter schema details
        params_schema = forecast_function.get('parameters', {})
        
        # Build a detailed prompt for the LLM with exact parameter requirements
        prompt = f"""Extract forest growth forecast parameters from this user request: "{user_query}"

You must extract exactly these three parameters:
- location: string (geographic location for the forecast)
- years: integer (number of years to forecast)
- include_human_impact: boolean (whether to include human impact in the forecast)

Return ONLY valid JSON in this exact format:
{{"location": "location name", "years": number, "include_human_impact": true/false}}

Examples:
- "forecast for Yellowstone for 10 years including human impact" → {{"location": "Yellowstone National Park", "years": 10, "include_human_impact": true}}
- "what will the forest look like in Colorado in 3 years without human factors" → {{"location": "Colorado", "years": 3, "include_human_impact": false}}

User request: "{user_query}"

Return only the JSON object:"""

        # Use LLM to extract parameters
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

        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = ForestGrowthParameters(**data)
            
            # Return in the required format with function name as top-level key
            return {
                "forest_growth_forecast": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract basic info with regex patterns
            location = "<UNKNOWN>"
            years = 5
            include_human_impact = True
            
            # Extract location patterns
            location_match = re.search(r'(?:in|for|at)\s+([A-Za-z\s]+?)(?:\s+(?:for|in|over|during)|$)', user_query, re.IGNORECASE)
            if location_match:
                location = location_match.group(1).strip()
            
            # Extract years/time patterns
            years_match = re.search(r'(\d+)\s*years?', user_query, re.IGNORECASE)
            if years_match:
                years = int(years_match.group(1))
            
            # Extract human impact preferences
            if re.search(r'without\s+human|no\s+human|exclude\s+human|natural\s+only', user_query, re.IGNORECASE):
                include_human_impact = False
            elif re.search(r'with\s+human|include\s+human|human\s+impact', user_query, re.IGNORECASE):
                include_human_impact = True
            
            return {
                "forest_growth_forecast": {
                    "location": location,
                    "years": years,
                    "include_human_impact": include_human_impact
                }
            }
            
    except Exception as e:
        # Ultimate fallback
        return {
            "forest_growth_forecast": {
                "location": "<UNKNOWN>",
                "years": 5,
                "include_human_impact": True
            }
        }