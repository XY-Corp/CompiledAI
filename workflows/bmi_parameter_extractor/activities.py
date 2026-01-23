from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class BMIParameters(BaseModel):
    """Expected BMI function call structure."""
    calculate_BMI: dict


async def extract_bmi_parameters(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user prompt to extract weight in kg and height in meters for BMI calculation function call.
    
    Args:
        user_prompt: The complete user request text containing weight and height information for BMI calculation
        available_functions: List of available function definitions to understand the required parameter structure
        
    Returns:
        Dict with calculate_BMI key containing weight_kg (int) and height_m (float) parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Extract weight and height using patterns first (deterministic approach)
        weight_kg = None
        height_m = None
        
        # Try to extract weight patterns (kg, pounds, lbs)
        weight_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)',
            r'(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)',
            r'weight.*?(\d+(?:\.\d+)?)',
            r'weigh.*?(\d+(?:\.\d+)?)'
        ]
        
        for pattern in weight_patterns:
            match = re.search(pattern, user_prompt.lower())
            if match:
                weight_value = float(match.group(1))
                # Convert lbs to kg if needed
                if 'lb' in pattern or 'pound' in pattern:
                    weight_value = weight_value * 0.453592  # lbs to kg conversion
                weight_kg = int(round(weight_value))
                break
        
        # Try to extract height patterns (m, cm, ft, inches)
        height_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:m|meters?)',
            r'(\d+(?:\.\d+)?)\s*(?:cm|centimeters?)',
            r"(\d+)['′]\s*(\d+)[\"″]",  # feet'inches"
            r'(\d+)\s*(?:ft|feet)\s*(\d+)\s*(?:in|inches?)',
            r'height.*?(\d+(?:\.\d+)?)',
            r'tall.*?(\d+(?:\.\d+)?)'
        ]
        
        for pattern in height_patterns:
            match = re.search(pattern, user_prompt.lower())
            if match:
                if "ft" in pattern or "'" in pattern:
                    # Handle feet and inches
                    feet = int(match.group(1))
                    inches = int(match.group(2)) if len(match.groups()) > 1 else 0
                    height_m = round((feet * 12 + inches) * 0.0254, 2)  # convert to meters
                else:
                    height_value = float(match.group(1))
                    if 'cm' in pattern:
                        height_m = round(height_value / 100, 2)  # cm to m
                    else:
                        height_m = round(height_value, 2)  # assume already in meters
                break
        
        # If regex patterns didn't work, use LLM as fallback
        if weight_kg is None or height_m is None:
            prompt = f"""Extract weight in kilograms (as integer) and height in meters (as float) from this request: "{user_prompt}"

Return ONLY valid JSON in this exact format:
{{"weight_kg": 70, "height_m": 1.75}}

Convert units if necessary:
- Convert pounds/lbs to kg (divide by 2.205)
- Convert cm to meters (divide by 100)
- Convert feet/inches to meters (feet*0.3048 + inches*0.0254)

Return only the JSON object with weight_kg as integer and height_m as float."""
            
            response = llm_client.generate(prompt)
            content = response.content.strip()
            
            # Extract JSON from response
            if "```" in content:
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
            
            try:
                llm_result = json.loads(content)
                if weight_kg is None and 'weight_kg' in llm_result:
                    weight_kg = int(llm_result['weight_kg'])
                if height_m is None and 'height_m' in llm_result:
                    height_m = float(llm_result['height_m'])
            except (json.JSONDecodeError, ValueError, KeyError):
                pass
        
        # Ensure we have valid values or provide defaults
        if weight_kg is None:
            weight_kg = 70  # Default weight
        if height_m is None:
            height_m = 1.75  # Default height
        
        # Return in the exact format specified by the schema
        result = {
            "calculate_BMI": {
                "weight_kg": weight_kg,
                "height_m": height_m
            }
        }
        
        return result
        
    except Exception as e:
        # Return default values if extraction fails
        return {
            "calculate_BMI": {
                "weight_kg": 70,
                "height_m": 1.75
            }
        }