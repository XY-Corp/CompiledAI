from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

async def extract_physics_parameters(
    problem_text: str,
    function_schema: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language physics problem to extract distance, duration, and determine appropriate unit for velocity calculation.
    
    Args:
        problem_text: The natural language physics problem containing distance, duration, and velocity calculation request
        function_schema: The available calculate_velocity function schema with parameter definitions for context
    
    Returns:
        Dict containing calculate_velocity key with nested object containing the extracted parameters
    """
    class VelocityParameters(BaseModel):
        """Define the expected velocity parameters structure."""
        distance: int
        duration: int
        unit: Optional[str] = None

    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)

        # Validate types
        if not isinstance(function_schema, list):
            return {"calculate_velocity": {"distance": 0, "duration": 1, "unit": "m/s"}}

        # Find the calculate_velocity function to understand its parameters
        calc_velocity_func = None
        for func in function_schema:
            if isinstance(func, dict) and func.get('name') == 'calculate_velocity':
                calc_velocity_func = func
                break

        if not calc_velocity_func:
            # Fallback if function not found - use default structure
            calc_velocity_func = {
                'parameters': {
                    'distance': {'type': 'int'},
                    'duration': {'type': 'int'},
                    'unit': {'type': 'string', 'required': False}
                }
            }

        # Format function details for LLM with EXACT parameter names
        params_schema = calc_velocity_func.get('parameters', calc_velocity_func.get('params', {}))
        param_details = []
        for param_name, param_info in params_schema.items():
            if isinstance(param_info, str):
                param_type = param_info
            else:
                param_type = param_info.get('type', 'string')
            param_details.append(f'"{param_name}": <{param_type}>')

        # Create clean prompt for LLM with exact parameter names
        prompt = f"""Extract velocity calculation parameters from this physics problem:
"{problem_text}"

Function calculate_velocity requires these EXACT parameter names:
{{{', '.join(param_details)}}}

Extract:
- distance: numerical value (convert to integer)
- duration: time period (convert to integer)  
- unit: velocity unit if specified (m/s, km/h, etc.) or determine appropriate unit

Return ONLY valid JSON in this exact format:
{{"distance": 100, "duration": 5, "unit": "m/s"}}"""

        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()

        # Remove markdown code blocks if present
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
            data = json.loads(content)
            
            # Ensure distance and duration are integers
            if 'distance' in data:
                data['distance'] = int(float(data['distance']))
            if 'duration' in data:
                data['duration'] = int(float(data['duration']))
            
            validated = VelocityParameters(**data)
            params_dict = validated.model_dump()
            
            # Remove None values for optional parameters
            if params_dict.get('unit') is None:
                params_dict.pop('unit', None)
                
            return {"calculate_velocity": params_dict}
            
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            # Fallback: try regex extraction from the problem text
            distance_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:meters?|m|km|kilometers?|miles?|feet?|ft)', problem_text, re.IGNORECASE)
            duration_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:seconds?|s|minutes?|min|hours?|h|hrs?)', problem_text, re.IGNORECASE)
            
            distance = int(float(distance_match.group(1))) if distance_match else 0
            duration = int(float(duration_match.group(1))) if duration_match else 1
            
            # Determine unit from text
            unit = None
            if 'km/h' in problem_text.lower() or 'kmh' in problem_text.lower():
                unit = 'km/h'
            elif 'mph' in problem_text.lower() or 'miles per hour' in problem_text.lower():
                unit = 'mph'
            elif 'm/s' in problem_text.lower():
                unit = 'm/s'
            
            result = {"distance": distance, "duration": duration}
            if unit:
                result["unit"] = unit
                
            return {"calculate_velocity": result}

    except Exception as e:
        # Return default values on any error
        return {"calculate_velocity": {"distance": 0, "duration": 1, "unit": "m/s"}}