from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class ElectricFieldParameters(BaseModel):
    """Expected parameters for electric field calculation."""
    charge: float
    distance: int
    medium: str = "vacuum"

async def extract_function_parameters(
    prompt_text: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language prompt to extract specific parameters (charge, distance, medium) needed for the electric field strength calculation"""
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # Ensure we have a prompt_text
        if not prompt_text or prompt_text.strip() == "null":
            prompt_text = ""
        
        # Extract the function schema details
        functions_list = function_schema if isinstance(function_schema, list) else [function_schema]
        
        # Find the electric field function
        target_function = None
        for func in functions_list:
            if func.get('name') == 'calculate_electric_field_strength':
                target_function = func
                break
        
        if not target_function:
            return {"calculate_electric_field_strength": {"error": "function not found"}}
        
        # Get parameters schema
        params_schema = target_function.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Create prompt for LLM to extract parameters
        prompt = f"""Extract parameters for electric field strength calculation from this text: "{prompt_text}"

The function requires these EXACT parameters:
- charge (float): The electric charge in Coulombs
- distance (integer): The distance in meters  
- medium (string, optional): The medium, defaults to "vacuum"

Look for:
- Charge values (may be in scientific notation like 1e-8, or with units like "0.01 C")
- Distance values (may have units like "4 m", "5 meters", "3m")
- Medium specifications (like "air", "vacuum", "water" - if not mentioned, use "vacuum")

Return ONLY valid JSON in this exact format:
{{"charge": <float_value>, "distance": <integer_value>, "medium": "<string_value>"}}

Examples:
- "charge of 0.01 C at distance 4 m" → {{"charge": 0.01, "distance": 4, "medium": "vacuum"}}
- "1e-6 Coulombs, 2 meters in air" → {{"charge": 0.000001, "distance": 2, "medium": "air"}}"""

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

        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = ElectricFieldParameters(**data)
            
            # Return in the exact format specified by the schema
            return {
                "calculate_electric_field_strength": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract with regex patterns
            charge_match = re.search(r'(?:charge|q)\s*[=:of]*\s*([0-9.e-]+)', prompt_text.lower())
            distance_match = re.search(r'(?:distance|d|at)\s*[=:of]*\s*([0-9.]+)\s*m', prompt_text.lower())
            medium_match = re.search(r'(?:in|medium)\s+(\w+)', prompt_text.lower())
            
            charge = float(charge_match.group(1)) if charge_match else 0.0
            distance = int(float(distance_match.group(1))) if distance_match else 1
            medium = medium_match.group(1) if medium_match else "vacuum"
            
            return {
                "calculate_electric_field_strength": {
                    "charge": charge,
                    "distance": distance,
                    "medium": medium
                }
            }

    except Exception as e:
        return {
            "calculate_electric_field_strength": {
                "charge": 0.0,
                "distance": 1,
                "medium": "vacuum"
            }
        }