from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class CellDensityParams(BaseModel):
    """Expected structure for calculate_cell_density function parameters."""
    optical_density: float
    dilution: int  
    calibration_factor: float = 1e9


async def extract_density_parameters(
    prompt_text: str,
    function_schema: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract optical density, dilution, and calibration factor parameters from natural language text using LLM for function call formatting.
    
    Args:
        prompt_text: The natural language text containing parameter values like optical density readings and dilution factors
        function_schema: JSON string describing the expected parameter structure and types for the calculate_cell_density function
        
    Returns:
        Function call structure: {"calculate_cell_density": {"optical_density": 0.6, "dilution": 5, "calibration_factor": 1000000000.0}}
    """
    try:
        # Parse the function schema if it's a JSON string
        if isinstance(function_schema, str):
            schema_data = json.loads(function_schema)
        else:
            schema_data = function_schema
            
        # Create a clear prompt for the LLM to extract parameters
        prompt = f"""Extract cell density calculation parameters from this text: "{prompt_text}"

Based on the function schema provided, extract these exact parameters:
- optical_density (float): The optical density measurement (OD value)
- dilution (integer): The dilution factor applied to the sample  
- calibration_factor (float): The calibration factor (default to 1000000000.0 if not specified)

Return ONLY valid JSON in this exact format:
{{"optical_density": <float_value>, "dilution": <integer_value>, "calibration_factor": <float_value>}}

Examples of what to look for:
- "OD is 0.6" → optical_density: 0.6
- "diluted 1:5" or "5x dilution" → dilution: 5
- "calibration factor 1e9" → calibration_factor: 1000000000.0

Text to analyze: {prompt_text}"""

        # Use the LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate the extracted parameters
        try:
            params_data = json.loads(content)
            validated_params = CellDensityParams(**params_data)
            
            # Return in the required format
            return {
                "calculate_cell_density": validated_params.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            optical_density = None
            dilution = None
            calibration_factor = 1e9  # Default value
            
            # Extract optical density
            od_patterns = [
                r'od[:\s]*(\d+\.?\d*)',
                r'optical\s+density[:\s]*(\d+\.?\d*)',
                r'absorbance[:\s]*(\d+\.?\d*)',
                r'(\d+\.?\d*)\s*od'
            ]
            
            for pattern in od_patterns:
                match = re.search(pattern, prompt_text.lower())
                if match:
                    optical_density = float(match.group(1))
                    break
            
            # Extract dilution
            dilution_patterns = [
                r'dilution[:\s]*(\d+)',
                r'diluted[:\s]*1:(\d+)',
                r'(\d+)x\s*dilution',
                r'1:(\d+)\s*dilution'
            ]
            
            for pattern in dilution_patterns:
                match = re.search(pattern, prompt_text.lower())
                if match:
                    dilution = int(match.group(1))
                    break
            
            # Extract calibration factor if present
            cal_patterns = [
                r'calibration[:\s]*factor[:\s]*(\d+\.?\d*(?:e[\+\-]?\d+)?)',
                r'cal[:\s]*factor[:\s]*(\d+\.?\d*(?:e[\+\-]?\d+)?)',
                r'factor[:\s]*(\d+\.?\d*(?:e[\+\-]?\d+)?)'
            ]
            
            for pattern in cal_patterns:
                match = re.search(pattern, prompt_text.lower())
                if match:
                    calibration_factor = float(match.group(1))
                    break
            
            # Use defaults if extraction failed
            if optical_density is None:
                optical_density = 0.0
            if dilution is None:
                dilution = 1
            
            return {
                "calculate_cell_density": {
                    "optical_density": optical_density,
                    "dilution": dilution,
                    "calibration_factor": calibration_factor
                }
            }
            
    except Exception as e:
        # Return default values if all else fails
        return {
            "calculate_cell_density": {
                "optical_density": 0.0,
                "dilution": 1,
                "calibration_factor": 1000000000.0
            }
        }