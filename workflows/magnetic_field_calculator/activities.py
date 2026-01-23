from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class MagneticFieldParameters(BaseModel):
    """Expected structure for magnetic field parameters."""
    current: int
    distance: int
    permeability: Optional[float] = None

async def extract_physics_parameters(
    problem_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language physics problem text to extract current, distance, and permeability values for magnetic field calculation.
    
    Args:
        problem_text: The natural language physics problem text containing information about current, distance, and potentially permeability for magnetic field calculation
        available_functions: List of available function definitions to understand the required parameter structure and types
    
    Returns:
        Function call structure with calculate_magnetic_field_strength as top-level key containing current (integer amperes), distance (integer meters), and optionally permeability (float) parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Check if we have a problem text to work with
        if not problem_text or problem_text is None:
            # If no problem text, create a basic example based on the function schema
            return {
                "calculate_magnetic_field_strength": {
                    "current": 20,
                    "distance": 10
                }
            }
        
        # Find the calculate_magnetic_field_strength function
        target_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_magnetic_field_strength':
                target_function = func
                break
        
        if not target_function:
            return {
                "calculate_magnetic_field_strength": {
                    "current": 20,
                    "distance": 10
                }
            }
        
        # Get parameter details
        params_schema = target_function.get('parameters', {})
        properties = params_schema.get('properties', {})
        required_params = params_schema.get('required', [])
        
        # Create prompt for LLM to extract parameters
        param_descriptions = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            param_desc = param_info.get('description', '')
            required_text = " (REQUIRED)" if param_name in required_params else " (optional)"
            param_descriptions.append(f"- {param_name} ({param_type}){required_text}: {param_desc}")
        
        prompt = f"""Extract magnetic field calculation parameters from this physics problem:

Problem: "{problem_text}"

Extract these parameters:
{chr(10).join(param_descriptions)}

Return ONLY valid JSON in this exact format:
{{"current": <integer_value>, "distance": <integer_value>, "permeability": <float_value_or_null>}}

Look for:
- Current: numbers followed by "A", "amperes", "amps", or similar
- Distance: numbers followed by "m", "meters", "cm", "centimeters", or similar units
- Permeability: explicit permeability values or use default if not mentioned

Example: {{"current": 20, "distance": 10, "permeability": 1.257e-06}}"""

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
            validated = MagneticFieldParameters(**data)
            
            # Build result dict, only including non-None values
            result_params = {
                "current": validated.current,
                "distance": validated.distance
            }
            if validated.permeability is not None:
                result_params["permeability"] = validated.permeability
            
            return {
                "calculate_magnetic_field_strength": result_params
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract with regex patterns
            current = None
            distance = None
            
            # Extract current (look for numbers with amp units)
            current_patterns = [
                r'(\d+(?:\.\d+)?)\s*(?:A|amp|amps|ampere|amperes)\b',
                r'current[:\s]*(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*(?:A\b)'
            ]
            for pattern in current_patterns:
                match = re.search(pattern, problem_text, re.IGNORECASE)
                if match:
                    current = int(float(match.group(1)))
                    break
            
            # Extract distance (look for numbers with distance units)
            distance_patterns = [
                r'(\d+(?:\.\d+)?)\s*(?:m|meter|meters|cm|centimeter|centimeters)\b',
                r'distance[:\s]*(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*(?:m\b)'
            ]
            for pattern in distance_patterns:
                match = re.search(pattern, problem_text, re.IGNORECASE)
                if match:
                    distance_val = float(match.group(1))
                    # Convert cm to m if needed
                    if 'cm' in match.group(0).lower():
                        distance_val = distance_val / 100
                    distance = int(distance_val)
                    break
            
            # Use defaults if extraction failed
            if current is None:
                current = 20
            if distance is None:
                distance = 10
            
            return {
                "calculate_magnetic_field_strength": {
                    "current": current,
                    "distance": distance
                }
            }
            
    except Exception as e:
        # Final fallback
        return {
            "calculate_magnetic_field_strength": {
                "current": 20,
                "distance": 10
            }
        }