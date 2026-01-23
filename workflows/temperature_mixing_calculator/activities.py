from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class TemperatureParameters(BaseModel):
    """Define the expected structure for temperature mixing parameters."""
    mass1: int
    temperature1: int
    mass2: int
    temperature2: int
    specific_heat_capacity: float = 4.2

async def extract_temperature_parameters(
    prompt_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts water mixing parameters (masses and temperatures) from natural language physics problem description.
    
    Args:
        prompt_text: Natural language description of water mixing temperature calculation problem containing masses and temperatures
    
    Returns:
        Dict with 'calculate_final_temperature' key containing extracted parameters
    """
    # Create a clear prompt for the LLM to extract temperature mixing parameters
    extraction_prompt = f"""Extract water mixing parameters from this physics problem:

{prompt_text}

You need to identify:
- mass1: mass of first water body (in kg, as integer)
- temperature1: temperature of first water body (in Celsius, as integer) 
- mass2: mass of second water body (in kg, as integer)
- temperature2: temperature of second water body (in Celsius, as integer)
- specific_heat_capacity: defaults to 4.2 kJ/kg/K for water

Return ONLY valid JSON in this exact format:
{{"mass1": 20, "temperature1": 30, "mass2": 15, "temperature2": 60, "specific_heat_capacity": 4.2}}

Do not include any explanations, just the JSON object."""

    # Use the injected LLM client to extract parameters
    response = llm_client.generate(extraction_prompt)
    
    # Extract JSON from response (handles markdown code blocks)
    content = response.content.strip()
    
    # Remove markdown code blocks if present
    if "```" in content:
        # Extract content between ```json and ``` or between ``` and ```
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
        validated = TemperatureParameters(**data)
        
        # Return in the exact format specified by the output schema
        return {
            "calculate_final_temperature": validated.model_dump()
        }
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback: try to extract numbers using regex patterns
        try:
            # Look for mass patterns (kg, grams, etc.)
            mass_pattern = r'(\d+(?:\.\d+)?)\s*(?:kg|grams?|g)\b'
            masses = [float(m) for m in re.findall(mass_pattern, prompt_text, re.IGNORECASE)]
            
            # Look for temperature patterns (celsius, degrees, C, etc.)
            temp_pattern = r'(\d+(?:\.\d+)?)\s*(?:°?[Cc]|degrees?|celsius)\b'
            temperatures = [float(t) for t in re.findall(temp_pattern, prompt_text, re.IGNORECASE)]
            
            # Convert grams to kg if needed
            for i, mass in enumerate(masses):
                if mass > 100:  # Likely in grams
                    masses[i] = mass / 1000
            
            if len(masses) >= 2 and len(temperatures) >= 2:
                return {
                    "calculate_final_temperature": {
                        "mass1": int(masses[0]),
                        "temperature1": int(temperatures[0]), 
                        "mass2": int(masses[1]),
                        "temperature2": int(temperatures[1]),
                        "specific_heat_capacity": 4.2
                    }
                }
            else:
                return {
                    "calculate_final_temperature": {
                        "mass1": 1,
                        "temperature1": 20,
                        "mass2": 1, 
                        "temperature2": 80,
                        "specific_heat_capacity": 4.2
                    }
                }
        except Exception:
            # Final fallback with default values
            return {
                "calculate_final_temperature": {
                    "mass1": 1,
                    "temperature1": 20,
                    "mass2": 1,
                    "temperature2": 80,
                    "specific_heat_capacity": 4.2
                }
            }