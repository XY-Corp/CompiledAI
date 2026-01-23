from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class ForestGrowthForecast(BaseModel):
    """Schema for forest growth forecast parameters."""
    location: str
    years: int
    include_human_impact: bool


async def extract_forecast_parameters(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function parameters from the user prompt for forest growth forecasting.
    
    Analyzes user input to extract location, timeframe, and human impact preferences
    for forest growth forecasting in Yellowstone National Park.
    
    Args:
        user_prompt: The raw user input containing the forest growth forecast request
        available_functions: List of available function definitions with their parameter schemas
        
    Returns:
        Dict containing forest_growth_forecast parameters with location, years, and include_human_impact
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
            return {"error": "forest_growth_forecast function not found in available functions"}
            
        # Get parameter schema details
        params_schema = forecast_function.get('parameters', {})
        
        # Build a detailed prompt for the LLM with exact parameter requirements
        prompt = f"""Extract forest growth forecast parameters from this user request: "{user_prompt}"

You must extract the following parameters for the forest_growth_forecast function:
- location: string (the geographic location for the forecast)
- years: integer (number of years to forecast)
- include_human_impact: boolean (whether to include human impact in the forecast)

Default assumptions if not specified:
- location: "Yellowstone National Park" (if no specific location mentioned)
- years: 10 (if no timeframe specified)
- include_human_impact: true (if not explicitly mentioned)

Return ONLY valid JSON in this exact format:
{{"location": "location_name", "years": 5, "include_human_impact": true}}"""

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
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = ForestGrowthForecast(**data)
            
            # Return in the exact format specified by the output schema
            return {
                "forest_growth_forecast": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            location_match = re.search(r'(?:in|at|for)\s+([^,\n]+(?:National Park|Park|Forest|region))', user_prompt, re.IGNORECASE)
            years_match = re.search(r'(\d+)\s*(?:years?|yr)', user_prompt, re.IGNORECASE)
            
            # Set defaults with extracted values
            location = location_match.group(1).strip() if location_match else "Yellowstone National Park"
            years = int(years_match.group(1)) if years_match else 10
            
            # Check for human impact mentions
            include_human_impact = True
            if re.search(r'(?:without|exclude|ignore).*(?:human|anthropogenic|development)', user_prompt, re.IGNORECASE):
                include_human_impact = False
            elif re.search(r'(?:natural|pristine|untouched).*(?:only|conditions)', user_prompt, re.IGNORECASE):
                include_human_impact = False
                
            return {
                "forest_growth_forecast": {
                    "location": location,
                    "years": years,
                    "include_human_impact": include_human_impact
                }
            }
            
    except Exception as e:
        return {"error": f"Failed to extract forecast parameters: {str(e)}"}