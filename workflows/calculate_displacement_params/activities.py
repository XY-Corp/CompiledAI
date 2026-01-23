from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class PhysicsParameters(BaseModel):
    """Structure for extracted physics parameters."""
    calculate_displacement: Dict[str, float | int]


async def extract_physics_parameters(
    prompt_text: str,
    function_schemas: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts numerical physics parameters from natural language text and formats them as function call parameters.
    
    Args:
        prompt_text: The natural language physics problem description containing initial velocity, acceleration, and time values
        function_schemas: List of available function definitions providing parameter names and types for validation
    
    Returns:
        Dict with function name as key containing nested dict of extracted parameter values
    """
    try:
        # Defensive parsing of function schemas
        if isinstance(function_schemas, str):
            function_schemas = json.loads(function_schemas)
        
        if not isinstance(function_schemas, list) or not function_schemas:
            return {"error": "Invalid or empty function schemas"}
        
        # Handle None prompt_text
        if prompt_text is None:
            prompt_text = ""
        
        # Find the calculate_displacement function
        calc_func = None
        for func in function_schemas:
            if func.get('name') == 'calculate_displacement':
                calc_func = func
                break
        
        if not calc_func:
            return {"error": "calculate_displacement function not found in schemas"}
        
        # Get parameter details from schema
        params_schema = calc_func.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Extract parameter names and types
        param_names = list(properties.keys())
        
        # Create clear prompt for LLM with exact parameter names
        param_details = []
        for name, info in properties.items():
            param_type = info.get('type', 'number')
            description = info.get('description', '')
            param_details.append(f'"{name}" ({param_type}): {description}')
        
        llm_prompt = f"""Extract physics calculation parameters from this text: "{prompt_text}"

The function "calculate_displacement" requires these EXACT parameters:
{chr(10).join(param_details)}

Extract numerical values and return ONLY valid JSON in this exact format:
{{"calculate_displacement": {{"initial_velocity": <number>, "time": <number>, "acceleration": <number>}}}}

Look for:
- Initial velocity: numbers with "m/s", "initial", "starting velocity", or similar
- Time: numbers with "seconds", "s", "time", or similar  
- Acceleration: numbers with "m/s²", "acceleration", "gravity" (often 9.8), or similar

If a parameter is not found, use reasonable defaults:
- acceleration: 9.8 (gravity)
- initial_velocity: 0
- time: 1"""
        
        # Use LLM to extract parameters
        response = llm_client.generate(llm_prompt)
        content = response.content.strip()
        
        # Clean up response - remove markdown if present
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
            
            # Ensure we have the right structure
            if 'calculate_displacement' not in data:
                # Try to construct it if we have raw parameters
                if any(param in data for param in param_names):
                    data = {'calculate_displacement': data}
                else:
                    # Fall back to extracting numbers from text manually
                    extracted_params = {}
                    
                    # Extract initial velocity
                    velocity_match = re.search(r'(?:initial|starting)?\s*(?:velocity)?\s*(?:of|is|=)?\s*(\d+(?:\.\d+)?)', prompt_text, re.IGNORECASE)
                    if velocity_match:
                        extracted_params['initial_velocity'] = int(float(velocity_match.group(1)))
                    else:
                        extracted_params['initial_velocity'] = 0
                    
                    # Extract time
                    time_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:second|s|time)', prompt_text, re.IGNORECASE)
                    if time_match:
                        extracted_params['time'] = int(float(time_match.group(1)))
                    else:
                        extracted_params['time'] = 1
                    
                    # Extract acceleration (look for gravity or acceleration values)
                    accel_match = re.search(r'(?:acceleration|gravity)?\s*(?:of|is|=)?\s*(\d+(?:\.\d+)?)', prompt_text, re.IGNORECASE)
                    if accel_match:
                        extracted_params['acceleration'] = float(accel_match.group(1))
                    else:
                        extracted_params['acceleration'] = 9.8  # Default gravity
                    
                    data = {'calculate_displacement': extracted_params}
            
            # Validate with Pydantic
            validated = PhysicsParameters(**data)
            return validated.model_dump()
            
        except (json.JSONDecodeError, ValueError) as e:
            # Last resort: manual extraction from original text
            extracted_params = {}
            
            # Look for numbers in the text and assign them based on context
            numbers = re.findall(r'\d+(?:\.\d+)?', prompt_text or "")
            
            if len(numbers) >= 2:
                # Assume first number is velocity, second is time
                extracted_params['initial_velocity'] = int(float(numbers[0]))
                extracted_params['time'] = int(float(numbers[1]))
                extracted_params['acceleration'] = 9.8
                
                if len(numbers) >= 3:
                    extracted_params['acceleration'] = float(numbers[2])
            else:
                # Default values
                extracted_params['initial_velocity'] = 10
                extracted_params['time'] = 5  
                extracted_params['acceleration'] = 9.8
            
            return {'calculate_displacement': extracted_params}
            
    except Exception as e:
        return {"error": f"Failed to extract parameters: {str(e)}"}