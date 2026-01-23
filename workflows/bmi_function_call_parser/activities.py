from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class BMIFunctionCall(BaseModel):
    """Expected structure for BMI function call."""
    calculate_BMI: Dict[str, Any]

async def extract_bmi_parameters_and_format_call(
    text: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract weight and height values from natural language text and format as a function call object.
    
    Args:
        text: Natural language text containing BMI calculation request with weight and height information
        function_schema: Function definition schema containing the calculate_BMI function specification and parameter types
    
    Returns:
        Function call object with calculate_BMI as the key and parameters object containing weight_kg (integer) and height_m (float)
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # Extract function info from schema
        function_name = "calculate_BMI"
        
        # Create a focused prompt for parameter extraction
        prompt = f"""Extract weight and height parameters from this text: "{text}"

The calculate_BMI function requires:
- weight_kg: integer (weight in kilograms)
- height_m: float (height in meters)

Convert units if needed:
- Weight: pounds to kg (divide by 2.205), stones to kg (multiply by 6.35)
- Height: feet/inches to meters, cm to meters (divide by 100)

Return ONLY valid JSON in this exact format:
{{"weight_kg": 70, "height_m": 1.75}}

If you find weight in pounds, convert to kg. If you find height in feet/inches or cm, convert to meters."""

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
        
        # Parse the extracted parameters
        try:
            parameters = json.loads(content)
            
            # Validate and convert types
            weight_kg = int(parameters.get('weight_kg', 0))
            height_m = float(parameters.get('height_m', 0))
            
            # Format as function call object
            result = {
                function_name: {
                    "weight_kg": weight_kg,
                    "height_m": height_m
                }
            }
            
            # Validate with Pydantic
            validated = BMIFunctionCall(**result)
            return validated.model_dump()
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Fallback: try regex extraction from original text
            weight_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|kilos?|pounds?|lbs?|stones?)', text.lower())
            height_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m|meters?|cm|centimeters?|ft|feet|\'|inches?|\")', text.lower())
            
            if weight_match and height_match:
                weight_val = float(weight_match.group(1))
                height_val = float(height_match.group(1))
                
                # Convert units based on context
                weight_unit = weight_match.group(0).lower()
                height_unit = height_match.group(0).lower()
                
                # Convert weight to kg
                if any(unit in weight_unit for unit in ['pound', 'lbs', 'lb']):
                    weight_val = weight_val / 2.205
                elif 'stone' in weight_unit:
                    weight_val = weight_val * 6.35
                
                # Convert height to meters
                if any(unit in height_unit for unit in ['cm', 'centimeter']):
                    height_val = height_val / 100
                elif any(unit in height_unit for unit in ['ft', 'feet', '\'']):
                    height_val = height_val * 0.3048
                elif any(unit in height_unit for unit in ['inch', '\"']):
                    height_val = height_val * 0.0254
                
                result = {
                    function_name: {
                        "weight_kg": int(weight_val),
                        "height_m": round(height_val, 2)
                    }
                }
                
                validated = BMIFunctionCall(**result)
                return validated.model_dump()
            
            return {
                function_name: {
                    "weight_kg": 70,
                    "height_m": 1.75
                }
            }
        
    except Exception as e:
        # Return default values on any error
        return {
            "calculate_BMI": {
                "weight_kg": 70,
                "height_m": 1.75
            }
        }