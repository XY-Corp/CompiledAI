from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class BMIFunctionCall(BaseModel):
    """Structure for BMI function call parameters."""
    weight: int
    height: int
    unit: str = "metric"

async def parse_bmi_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language BMI request and extract weight and height values to map to the calculate_bmi function.
    
    Args:
        user_request: The complete user request text containing weight and height information to be parsed for BMI calculation
        available_functions: List of available function definitions providing parameter schemas and validation context
        
    Returns:
        Dict containing calculate_bmi key with weight, height, and unit parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        if not isinstance(available_functions, list):
            return {"calculate_bmi": {"weight": 0, "height": 0, "unit": "metric"}}
        
        # Find the calculate_bmi function in the available functions list
        calculate_bmi_func = None
        for func in available_functions:
            if isinstance(func, dict) and func.get('name') == 'calculate_bmi':
                calculate_bmi_func = func
                break
                
        if not calculate_bmi_func:
            # Fallback to parsing without schema validation
            return await _parse_bmi_fallback(user_request)
        
        # Extract parameter schema for calculate_bmi
        params_schema = calculate_bmi_func.get('parameters', {})
        
        # Create a clear prompt for the LLM to extract BMI parameters
        prompt = f"""Extract weight and height values from this BMI calculation request: "{user_request}"

The calculate_bmi function requires these EXACT parameters:
- weight: integer (in kg if metric, lbs if imperial)
- height: integer (in cm if metric, inches if imperial)  
- unit: string ("metric" or "imperial", default "metric")

Look for patterns like:
- "weight 85kg height 180cm" → weight: 85, height: 180, unit: "metric"
- "weigh 185 pounds, 6 feet tall" → weight: 185, height: 72, unit: "imperial" (6 feet = 72 inches)
- "75kg and 175cm" → weight: 75, height: 175, unit: "metric"

Return ONLY valid JSON in this exact format:
{{"weight": 85, "height": 180, "unit": "metric"}}"""

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
        try:
            data = json.loads(content)
            validated = BMIFunctionCall(**data)
            return {"calculate_bmi": validated.model_dump()}
        except (json.JSONDecodeError, ValueError):
            # Fallback to regex parsing
            return await _parse_bmi_fallback(user_request)
            
    except Exception as e:
        # Return default values on any error
        return {"calculate_bmi": {"weight": 0, "height": 0, "unit": "metric"}}

async def _parse_bmi_fallback(user_request: str) -> dict[str, Any]:
    """Fallback regex-based parsing for BMI parameters."""
    try:
        weight = 0
        height = 0
        unit = "metric"
        
        # Convert to lowercase for easier matching
        text = user_request.lower()
        
        # Look for weight patterns
        weight_patterns = [
            r'weight\s*:?\s*(\d+)\s*(kg|pounds?|lbs?)?',
            r'weigh\s*(\d+)\s*(kg|pounds?|lbs?)?',
            r'(\d+)\s*(kg|pounds?|lbs?)\s*weight',
            r'(\d+)\s*(kg|pounds?|lbs?)',
        ]
        
        for pattern in weight_patterns:
            match = re.search(pattern, text)
            if match:
                weight = int(match.group(1))
                weight_unit = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                if weight_unit and any(u in weight_unit for u in ['pound', 'lbs', 'lb']):
                    unit = "imperial"
                break
        
        # Look for height patterns
        height_patterns = [
            r'height\s*:?\s*(\d+)\s*(cm|inches?|in|feet?|ft)?',
            r'tall\s*(\d+)\s*(cm|inches?|in|feet?|ft)?',
            r'(\d+)\s*(cm|inches?|in|feet?|ft)\s*tall',
            r'(\d+)\s*(cm|inches?|in)',
            r'(\d+)\s*feet?\s*(\d*)\s*inches?',  # "6 feet 2 inches"
        ]
        
        for pattern in height_patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) >= 3 and match.group(3):  # feet and inches
                    feet = int(match.group(1))
                    inches = int(match.group(2)) if match.group(2) else 0
                    height = feet * 12 + inches
                    unit = "imperial"
                else:
                    height = int(match.group(1))
                    height_unit = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                    if height_unit:
                        if any(u in height_unit for u in ['inch', 'in']):
                            unit = "imperial"
                        elif 'feet' in height_unit or 'ft' in height_unit:
                            height = height * 12  # convert feet to inches
                            unit = "imperial"
                break
        
        return {"calculate_bmi": {"weight": weight, "height": height, "unit": unit}}
        
    except Exception:
        return {"calculate_bmi": {"weight": 0, "height": 0, "unit": "metric"}}