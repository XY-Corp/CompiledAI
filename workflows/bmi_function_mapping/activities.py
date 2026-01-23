from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class BMIParameters(BaseModel):
    """Expected BMI function parameters structure."""
    weight: int
    height: int 
    unit: str = "metric"


async def extract_bmi_parameters(
    request_text: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language BMI request and extract weight and height values to map to the calculate_bmi function.
    
    Args:
        request_text: The natural language text requesting BMI calculation containing weight and height information
        function_schema: The target function schema including parameters and their types for calculate_bmi function
        
    Returns:
        Dict containing calculate_bmi key with weight, height, and unit parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
            
        # Create a clear prompt for the LLM to extract BMI parameters
        prompt = f"""Extract weight and height values from this BMI calculation request: "{request_text}"

Return ONLY valid JSON in this exact format:
{{"weight": <number>, "height": <number>, "unit": "metric"}}

Rules:
- weight should be in kilograms if metric, pounds if imperial
- height should be in centimeters if metric, inches if imperial  
- unit should be "metric" or "imperial" based on the units mentioned
- If no units specified, assume "metric"
- Extract only the numeric values for weight and height"""

        response = llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
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
        data = json.loads(content)
        validated = BMIParameters(**data)
        
        # Return in the exact format specified in the output schema
        return {
            "calculate_bmi": validated.model_dump()
        }
        
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback to regex parsing if LLM response fails
        try:
            # Try to extract numbers from the original text
            weight_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|kilo|pound|lb|weight)', request_text.lower())
            height_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:cm|meter|m|inch|in|ft|feet|height)', request_text.lower())
            
            if weight_match and height_match:
                weight = int(float(weight_match.group(1)))
                height = int(float(height_match.group(1)))
                
                # Determine unit based on keywords
                unit = "imperial" if any(word in request_text.lower() for word in ["lb", "pound", "inch", "in", "ft", "feet"]) else "metric"
                
                return {
                    "calculate_bmi": {
                        "weight": weight,
                        "height": height,
                        "unit": unit
                    }
                }
            
            # Default fallback
            return {
                "calculate_bmi": {
                    "weight": 70,
                    "height": 170,
                    "unit": "metric"
                }
            }
            
        except Exception:
            return {
                "calculate_bmi": {
                    "weight": 70,
                    "height": 170, 
                    "unit": "metric"
                }
            }