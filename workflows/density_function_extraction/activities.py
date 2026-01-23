from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class DensityFunction(BaseModel):
    """Expected structure for density function call."""
    calculate_density: Dict[str, Any]

async def extract_density_params(
    text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language text to extract mass, volume, and unit parameters for density calculation and format them into a function call structure.
    
    Args:
        text: The natural language text containing the density calculation question with mass and volume values
        
    Returns:
        Dict with 'calculate_density' as key and parameters dict containing mass, volume, and unit
    """
    try:
        # Use LLM to extract density parameters from natural language text
        prompt = f"""Extract the density calculation parameters from this text: {text}

The text contains a density calculation question with mass and volume values.
Extract these parameters and format them as a function call.

Return ONLY valid JSON in this exact format:
{{"calculate_density": {{"mass": <integer_value>, "volume": <integer_value>, "unit": "kg/m³"}}}}

Examples:
- "What is the density if mass is 45 kg and volume is 15 m³?" → {{"calculate_density": {{"mass": 45, "volume": 15, "unit": "kg/m³"}}}}
- "Calculate density for mass 30 and volume 10" → {{"calculate_density": {{"mass": 30, "volume": 10, "unit": "kg/m³"}}}}

Return only the JSON object, no explanations."""

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

        # Parse and validate with Pydantic
        data = json.loads(content)
        validated = DensityFunction(**data)
        return validated.model_dump()

    except (json.JSONDecodeError, ValueError) as e:
        # Fallback: Try regex extraction as backup
        try:
            # Look for mass and volume numbers in the text
            mass_match = re.search(r'mass\s*(?:is|=)?\s*(\d+)', text, re.IGNORECASE)
            volume_match = re.search(r'volume\s*(?:is|=)?\s*(\d+)', text, re.IGNORECASE)
            
            if mass_match and volume_match:
                mass = int(mass_match.group(1))
                volume = int(volume_match.group(1))
                
                return {
                    "calculate_density": {
                        "mass": mass,
                        "volume": volume,
                        "unit": "kg/m³"
                    }
                }
            else:
                return {
                    "calculate_density": {
                        "mass": 0,
                        "volume": 1,
                        "unit": "kg/m³"
                    }
                }
        except Exception:
            # Final fallback with default values
            return {
                "calculate_density": {
                    "mass": 0,
                    "volume": 1,
                    "unit": "kg/m³"
                }
            }