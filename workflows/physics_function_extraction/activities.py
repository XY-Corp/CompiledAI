from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class PhysicsParameters(BaseModel):
    """Expected structure for physics function call."""
    calculate_final_speed: Dict[str, float]


async def extract_physics_parameters(
    question_text: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the physics question to extract parameter values for the calculate_final_speed function, identifying time, initial speed, and gravity values from the user's question text.

    Args:
        question_text: The complete physics question text containing the problem statement with numerical values and conditions
        function_schema: The schema definition for the calculate_final_speed function including parameter names, types, and descriptions

    Returns:
        Dict containing calculate_final_speed as key with extracted parameters as nested object
    """
    try:
        # Parse JSON string input if needed
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
            
        # Handle case where function_schema is a list containing the schema
        if isinstance(function_schema, list) and len(function_schema) > 0:
            function_schema = function_schema[0]
        
        # Get parameter details from schema
        params_info = function_schema.get('parameters', function_schema.get('params', {}))
        
        # Create prompt for LLM with explicit parameter names
        param_names = list(params_info.keys())
        
        prompt = f"""Extract physics parameters from this question: "{question_text}"

The calculate_final_speed function requires these EXACT parameters:
- initial_speed: initial velocity (m/s), default 0 for objects starting from rest
- time: time duration (seconds) 
- gravity: gravitational acceleration (m/s²), default -9.81 for Earth

Extract numerical values from the question. If a parameter isn't mentioned:
- initial_speed: use 0 (object starts from rest)
- gravity: use -9.81 (Earth's gravity)

Return ONLY valid JSON in this exact format:
{{"initial_speed": 0, "time": 5, "gravity": -9.81}}

Do not include any explanations, just the JSON object with the three parameters."""

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

        # Parse and validate extracted parameters
        try:
            extracted_params = json.loads(content)
            
            # Ensure all required parameters are present with defaults
            final_params = {
                "initial_speed": extracted_params.get("initial_speed", 0),
                "time": extracted_params.get("time", 0), 
                "gravity": extracted_params.get("gravity", -9.81)
            }
            
            # Validate with Pydantic
            result_data = {"calculate_final_speed": final_params}
            validated = PhysicsParameters(**result_data)
            
            return validated.model_dump()
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract numbers using regex
            numbers = re.findall(r'-?\d+\.?\d*', question_text)
            
            # Default parameters
            params = {
                "initial_speed": 0,  # Default for objects starting from rest
                "time": float(numbers[0]) if numbers else 0,  # First number likely time
                "gravity": -9.81  # Earth's gravity
            }
            
            # Look for specific patterns
            if "initial" in question_text.lower() or "starts with" in question_text.lower():
                if len(numbers) >= 2:
                    params["initial_speed"] = float(numbers[0])
                    params["time"] = float(numbers[1])
            
            return {"calculate_final_speed": params}

    except Exception as e:
        # Return default physics parameters if all else fails
        return {
            "calculate_final_speed": {
                "initial_speed": 0,
                "time": 0,
                "gravity": -9.81
            }
        }