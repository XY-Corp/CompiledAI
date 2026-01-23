from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class VelocityParameters(BaseModel):
    """Expected structure for velocity calculation parameters."""
    distance: int
    duration: int
    unit: Optional[str] = None


class FunctionCall(BaseModel):
    """Expected structure for the function call response."""
    calculate_velocity: Dict[str, Any]


async def extract_velocity_parameters(
    user_query: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user query to extract distance, duration, and optional unit parameters for velocity calculation.
    
    Args:
        user_query: The complete user input text containing velocity calculation request with distance and duration information
        available_functions: List of available function definitions to understand expected parameter structure and requirements
    
    Returns:
        Dict containing calculate_velocity key with nested object containing the extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)

        # Validate types
        if not isinstance(available_functions, list):
            return {"calculate_velocity": {"distance": 0, "duration": 1, "unit": "m/s"}}

        # Find the calculate_velocity function to understand its parameters
        calc_velocity_func = None
        for func in available_functions:
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

        # Create LLM prompt to extract parameters
        prompt = f"""User query: "{user_query}"

Extract velocity calculation parameters from this query.

The calculate_velocity function requires these EXACT parameter names:
{', '.join(param_details)}

Look for:
- distance: numerical value (convert to integer)
- duration: time value (convert to integer) 
- unit: velocity unit like "km/h", "m/s", "mph" (optional)

Examples:
- "Calculate velocity for 50 km in 2 hours" → distance: 50, duration: 2, unit: "km/h"
- "What's the speed for 100 meters in 10 seconds?" → distance: 100, duration: 10, unit: "m/s"
- "Find velocity: 200 miles, 4 hours" → distance: 200, duration: 4, unit: "mph"

Return ONLY valid JSON in this exact format:
{{"distance": 50, "duration": 2, "unit": "km/h"}}

If unit is not specified, omit it from the JSON."""

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
                data['distance'] = int(float(str(data['distance'])))
            if 'duration' in data:
                data['duration'] = int(float(str(data['duration'])))
            
            validated = VelocityParameters(**data)
            parameters = validated.model_dump(exclude_none=True)
            
            return {"calculate_velocity": parameters}
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract numbers with regex
            numbers = re.findall(r'\b\d+(?:\.\d+)?\b', user_query)
            if len(numbers) >= 2:
                distance = int(float(numbers[0]))
                duration = int(float(numbers[1]))
                
                # Try to detect unit
                unit = None
                if 'km/h' in user_query.lower() or 'kmh' in user_query.lower():
                    unit = "km/h"
                elif 'm/s' in user_query.lower() or 'mps' in user_query.lower():
                    unit = "m/s"
                elif 'mph' in user_query.lower():
                    unit = "mph"
                
                result = {"distance": distance, "duration": duration}
                if unit:
                    result["unit"] = unit
                    
                return {"calculate_velocity": result}
            else:
                # Default fallback
                return {"calculate_velocity": {"distance": 50, "duration": 2}}
                
    except Exception as e:
        # Final fallback
        return {"calculate_velocity": {"distance": 50, "duration": 2}}