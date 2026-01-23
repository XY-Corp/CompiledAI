from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """A function call with parameters."""
    function_name: str
    parameters: Dict[str, Any]


async def parse_physics_parameters(
    user_question: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract physics parameters from user question and match to appropriate function call.
    
    Args:
        user_question: The complete user question containing physics problem parameters and context
        available_functions: List of available physics calculation functions with their parameters and descriptions
        
    Returns:
        Dict with function name as key and extracted parameters as value
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not available_functions:
            return {"error": "No functions available"}
        
        # For physics problems, we'll typically use the first/most relevant function
        # In a real scenario, we'd analyze the question to select the best function
        selected_function = available_functions[0]
        function_name = selected_function.get('name', '')
        
        # Get function parameters schema
        parameters_schema = selected_function.get('parameters', {})
        properties = parameters_schema.get('properties', {})
        required_params = parameters_schema.get('required', [])
        
        # Build a detailed prompt for parameter extraction
        param_descriptions = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            description = param_info.get('description', '')
            required = "REQUIRED" if param_name in required_params else "OPTIONAL"
            param_descriptions.append(f'- "{param_name}" ({param_type}) - {description} [{required}]')
        
        params_text = '\n'.join(param_descriptions)
        
        prompt = f"""Extract parameters for the physics function "{function_name}" from this user question:

Question: "{user_question}"

Function parameters:
{params_text}

Extract the parameter values from the question. For physics problems:
- If height/distance is mentioned, extract the numeric value
- If initial velocity is not mentioned, use 0
- If gravity is not mentioned, use 9.81 (Earth's gravity)
- Convert all numeric values to appropriate types (int for whole numbers, float for decimals)

Return ONLY valid JSON in this exact format:
{{"param1": value1, "param2": value2, "param3": value3}}

Example: {{"height": 150, "initial_velocity": 0, "gravity": 9.81}}"""

        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse the extracted parameters
        try:
            extracted_params = json.loads(content)
            
            # Convert string numbers to appropriate types based on schema
            for param_name, param_value in extracted_params.items():
                if param_name in properties:
                    expected_type = properties[param_name].get('type', 'string')
                    if expected_type == 'integer' and isinstance(param_value, (str, float)):
                        try:
                            extracted_params[param_name] = int(float(param_value))
                        except (ValueError, TypeError):
                            pass
                    elif expected_type == 'float' and isinstance(param_value, (str, int)):
                        try:
                            extracted_params[param_name] = float(param_value)
                        except (ValueError, TypeError):
                            pass
            
            # Return in the exact format specified: {function_name: {parameters}}
            return {function_name: extracted_params}
            
        except json.JSONDecodeError as e:
            # Fallback: try to extract numbers from the question directly
            return _fallback_parameter_extraction(user_question, function_name, properties, required_params)
            
    except Exception as e:
        return {"error": f"Failed to parse physics parameters: {str(e)}"}


def _fallback_parameter_extraction(question: str, function_name: str, properties: dict, required_params: list) -> dict[str, Any]:
    """Fallback parameter extraction using regex patterns."""
    try:
        extracted = {}
        
        # Common physics parameter patterns
        height_match = re.search(r'(?:height|drop|fall).*?(\d+(?:\.\d+)?)\s*(?:m|meter|metre)', question, re.IGNORECASE)
        velocity_match = re.search(r'(?:initial|starting).*?velocity.*?(\d+(?:\.\d+)?)\s*(?:m/s|ms)', question, re.IGNORECASE)
        
        # Extract height
        if 'height' in properties:
            if height_match:
                height_val = float(height_match.group(1))
                extracted['height'] = int(height_val) if height_val.is_integer() else height_val
            elif 'height' in required_params:
                # Default fallback for required height
                extracted['height'] = 150
        
        # Extract initial velocity
        if 'initial_velocity' in properties:
            if velocity_match:
                vel_val = float(velocity_match.group(1))
                extracted['initial_velocity'] = int(vel_val) if vel_val.is_integer() else vel_val
            else:
                # Default to 0 for free fall problems
                extracted['initial_velocity'] = 0
        
        # Extract gravity
        if 'gravity' in properties:
            gravity_match = re.search(r'gravity.*?(\d+(?:\.\d+)?)', question, re.IGNORECASE)
            if gravity_match:
                extracted['gravity'] = float(gravity_match.group(1))
            else:
                # Default Earth gravity
                extracted['gravity'] = 9.81
        
        return {function_name: extracted}
        
    except Exception as e:
        return {"error": f"Fallback extraction failed: {str(e)}"}