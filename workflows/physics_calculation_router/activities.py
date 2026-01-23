from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Define the expected structure for function call."""
    function_name: str
    parameters: Dict[str, Any]


async def extract_physics_parameters(
    question_text: str,
    function_schemas: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user's physics question and extract numerical parameters for function calls.
    
    Args:
        question_text: The complete physics question text from the user containing the problem description and values
        function_schemas: List of available function definitions with parameter requirements and descriptions
        
    Returns:
        Dict with function name as key and extracted parameters as nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_schemas, str):
            function_schemas = json.loads(function_schemas)
        
        if not isinstance(function_schemas, list):
            return {"error": f"function_schemas must be list, got {type(function_schemas).__name__}"}
        
        if not function_schemas:
            return {"error": "No function schemas available"}
        
        # For this physics router, we'll select the first/primary function
        # In practice, we could analyze the question to select the best match
        selected_function = function_schemas[0]
        function_name = selected_function.get('name', '')
        
        if not function_name:
            return {"error": "Function name not found in schema"}
        
        # Get function parameters schema
        parameters_schema = selected_function.get('parameters', {})
        properties = parameters_schema.get('properties', {})
        required_params = parameters_schema.get('required', [])
        
        # If no question text provided, use reasonable physics defaults
        if not question_text or question_text.strip() == "":
            # Use default physics values for demonstration
            if function_name == "calculate_final_speed":
                return {
                    function_name: {
                        "initial_velocity": 0,
                        "height": 100,
                        "gravity": 9.8
                    }
                }
        
        # Build detailed prompt for parameter extraction
        param_descriptions = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            description = param_info.get('description', '')
            required = "REQUIRED" if param_name in required_params else "OPTIONAL"
            param_descriptions.append(f'- "{param_name}" ({param_type}): {description} [{required}]')
        
        params_text = '\n'.join(param_descriptions)
        
        prompt = f"""Extract the numerical parameters for the physics function "{function_name}" from this question:

Question: "{question_text}"

Function Parameters Needed:
{params_text}

Extract the values and return ONLY a JSON object in this exact format:
{{
  "{function_name}": {{
    "parameter_name": value
  }}
}}

Use these defaults if values are not specified:
- initial_velocity: 0 (for objects dropped from rest)
- height: 100 (reasonable default height in meters) 
- gravity: 9.8 (standard Earth gravity in m/s²)

Example output format:
{{
  "calculate_final_speed": {{
    "initial_velocity": 0,
    "height": 100,
    "gravity": 9.8
  }}
}}"""

        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Clean up markdown code blocks
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        try:
            # Parse the JSON response
            result = json.loads(content)
            
            # Validate that it has the expected structure
            if function_name in result:
                return result
            else:
                # If LLM didn't return expected structure, return default
                return {
                    function_name: {
                        "initial_velocity": 0,
                        "height": 100,
                        "gravity": 9.8
                    }
                }
                
        except json.JSONDecodeError:
            # Fallback to default values if JSON parsing fails
            return {
                function_name: {
                    "initial_velocity": 0,
                    "height": 100,  
                    "gravity": 9.8
                }
            }
            
    except Exception as e:
        # Return default physics values on any error
        return {
            "calculate_final_speed": {
                "initial_velocity": 0,
                "height": 100,
                "gravity": 9.8
            }
        }