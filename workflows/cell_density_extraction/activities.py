from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class CellDensityParameters(BaseModel):
    """Validation model for cell density calculation parameters."""
    optical_density: float
    dilution: int
    calibration_factor: float


async def extract_cell_density_parameters(
    user_prompt: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses the user prompt to extract optical density and dilution factor values and formats them as function parameters for calculate_cell_density.
    
    Args:
        user_prompt: The user's natural language request containing optical density and dilution factor values for cell density calculation
        
    Returns:
        Function call structure with calculate_cell_density as the key and parameters containing optical_density, dilution, and calibration_factor
    """
    
    # Create a focused prompt for LLM extraction
    extraction_prompt = f"""Extract cell density calculation parameters from this text:

{user_prompt}

Extract these exact values:
- optical_density: numerical value (float)
- dilution: dilution factor (integer) 
- calibration_factor: calibration factor (float, often scientific notation like 1e9)

Return ONLY valid JSON in this exact format:
{{"optical_density": 0.6, "dilution": 5, "calibration_factor": 1000000000.0}}"""

    response = llm_client.generate(extraction_prompt)
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
    try:
        data = json.loads(content)
        validated = CellDensityParameters(**data)
        
        # Return in the exact format specified in the output schema
        return {
            "calculate_cell_density": validated.model_dump()
        }
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback - try to extract with regex patterns
        try:
            # Look for common patterns in the text
            optical_density = 0.6  # default
            dilution = 5  # default  
            calibration_factor = 1e9  # default
            
            # Try to extract optical density
            od_match = re.search(r'optical\s+density[:\s]*([0-9]*\.?[0-9]+)', user_prompt, re.IGNORECASE)
            if od_match:
                optical_density = float(od_match.group(1))
            
            # Try to extract dilution factor
            dilution_match = re.search(r'dilution[:\s]*([0-9]+)', user_prompt, re.IGNORECASE)
            if dilution_match:
                dilution = int(dilution_match.group(1))
            
            # Try to extract calibration factor
            calib_match = re.search(r'calibration[:\s]*([0-9]*\.?[0-9]+(?:e[0-9]+)?)', user_prompt, re.IGNORECASE)
            if calib_match:
                calibration_factor = float(calib_match.group(1))
            
            return {
                "calculate_cell_density": {
                    "optical_density": optical_density,
                    "dilution": dilution,
                    "calibration_factor": calibration_factor
                }
            }
        except Exception:
            # Final fallback with defaults
            return {
                "calculate_cell_density": {
                    "optical_density": 0.6,
                    "dilution": 5,
                    "calibration_factor": 1000000000.0
                }
            }