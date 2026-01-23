from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class DiabetesParameters(BaseModel):
    """Expected diabetes prediction parameters."""
    weight: int
    height: int
    activity_level: str

async def extract_health_parameters(
    user_query: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract weight, height, and activity level from user query and format as function call.
    
    Args:
        user_query: The complete user query containing health information like weight, height, and activity level
        function_schema: The diabetes_prediction function schema with parameter definitions and validation rules
    
    Returns:
        Dict with diabetes_prediction function call containing extracted parameters
    """
    try:
        # Parse JSON string if needed
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # Extract function definition - handle both single function and list of functions
        if isinstance(function_schema, list):
            # Find diabetes_prediction function
            diabetes_func = None
            for func in function_schema:
                if func.get('name') == 'diabetes_prediction':
                    diabetes_func = func
                    break
            
            if not diabetes_func:
                return {"error": "diabetes_prediction function not found in schema"}
                
            function_params = diabetes_func.get('parameters', {})
        else:
            # Single function case
            function_params = function_schema.get('parameters', {})
        
        # Get activity level enum options from schema
        activity_levels = ["sedentary", "lightly active", "moderately active", "very active", "extra active"]
        if 'properties' in function_params and 'activity_level' in function_params['properties']:
            enum_values = function_params['properties']['activity_level'].get('enum', activity_levels)
            activity_levels = enum_values
        
        # Create a structured prompt for LLM to extract parameters
        prompt = f"""Extract health parameters from this user query: "{user_query}"

Extract the following information:
1. Weight in pounds (integer)
2. Height in inches (integer) 
3. Activity level from these options: {', '.join(activity_levels)}

Return ONLY valid JSON in this exact format:
{{"weight": <integer>, "height": <integer>, "activity_level": "<string>"}}

If height is given in feet and inches (like 5'10"), convert to total inches.
If weight is missing, use a reasonable default like 150.
If height is missing, use a reasonable default like 70 inches.
If activity level is missing, use "lightly active".
"""

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
            validated = DiabetesParameters(**data)
            parameters = validated.model_dump()
            
            # Return in the exact format specified by the output schema
            return {
                "diabetes_prediction": parameters
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            weight = None
            height = None
            activity_level = "lightly active"
            
            # Extract weight (look for numbers followed by lb, lbs, pounds, etc.)
            weight_match = re.search(r'(\d+)\s*(?:lb|lbs|pounds?)', user_query.lower())
            if weight_match:
                weight = int(weight_match.group(1))
            else:
                # Look for any number that might be weight
                numbers = re.findall(r'\b(\d+)\b', user_query)
                if numbers:
                    weight = int(numbers[0])  # Take first number as weight
                else:
                    weight = 150  # Default
            
            # Extract height (look for feet/inches pattern or just inches)
            height_match = re.search(r"(\d+)(?:'|ft|feet)\s*(\d+)(?:\"|in|inches?)?", user_query.lower())
            if height_match:
                feet = int(height_match.group(1))
                inches = int(height_match.group(2))
                height = feet * 12 + inches
            else:
                # Look for inches only
                inches_match = re.search(r'(\d+)\s*(?:"|in|inches?)', user_query.lower())
                if inches_match:
                    height = int(inches_match.group(1))
                else:
                    height = 70  # Default
            
            # Extract activity level
            query_lower = user_query.lower()
            for level in activity_levels:
                if level.lower() in query_lower:
                    activity_level = level
                    break
            
            return {
                "diabetes_prediction": {
                    "weight": weight,
                    "height": height,
                    "activity_level": activity_level
                }
            }
            
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}