from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class SineWaveParameters(BaseModel):
    """Schema for sine wave plotting parameters."""
    start_range: float = 0.0
    end_range: float = 6.2832
    frequency: int = 1
    amplitude: float = 1.0
    phase_shift: float = 0.0

async def parse_sine_wave_parameters(
    command_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse natural language command to extract sine wave plotting parameters and format as function call.
    
    Args:
        command_text: The natural language command containing sine wave parameters
        available_functions: List of available function definitions
        
    Returns:
        Dict with function name as key and parameters dict as value
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Find the plot_sine_wave function to understand its schema
        plot_function = None
        for func in available_functions:
            if func.get('name') == 'plot_sine_wave':
                plot_function = func
                break
        
        if not plot_function:
            return {"plot_sine_wave": {}}
        
        # Get parameter schema
        params_schema = plot_function.get('parameters', {})
        properties = params_schema.get('properties', {}) if isinstance(params_schema, dict) else {}
        
        # Format function schema clearly for LLM
        param_details = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'number')
            description = param_info.get('description', '')
            param_details.append(f"- {param_name} ({param_type}): {description}")
        
        schema_text = "\n".join(param_details) if param_details else """
- start_range (number): Starting value for the range
- end_range (number): Ending value for the range  
- frequency (number): Frequency of the sine wave
- amplitude (number): Amplitude of the sine wave
- phase_shift (number): Phase shift of the sine wave"""
        
        # Create prompt for LLM to extract parameters
        prompt = f"""Extract sine wave plotting parameters from this command: "{command_text}"

Function: plot_sine_wave
Parameters needed:
{schema_text}

Parse the command and extract numerical values for each parameter. If a parameter is not specified, use these defaults:
- start_range: 0.0
- end_range: 6.2832 (2π)
- frequency: 1
- amplitude: 1.0  
- phase_shift: 0.0

Return ONLY valid JSON in this exact format:
{{"start_range": 0.0, "end_range": 6.2832, "frequency": 1, "amplitude": 1.0, "phase_shift": 0.0}}"""

        response = llm_client.generate(prompt)
        
        # Extract JSON from response (handle markdown code blocks)
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
            validated = SineWaveParameters(**data)
            parameters = validated.model_dump()
            
            # Return in the exact format specified: function name as top-level key
            return {"plot_sine_wave": parameters}
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract numbers from command text using regex
            return _extract_parameters_with_regex(command_text)
            
    except Exception as e:
        # Return default parameters if all parsing fails
        return {"plot_sine_wave": {
            "start_range": 0.0,
            "end_range": 6.2832,
            "frequency": 1,
            "amplitude": 1.0,
            "phase_shift": 0.0
        }}

def _extract_parameters_with_regex(command_text: str) -> dict[str, Any]:
    """Fallback method to extract parameters using regex patterns."""
    parameters = {
        "start_range": 0.0,
        "end_range": 6.2832,
        "frequency": 1,
        "amplitude": 1.0,
        "phase_shift": 0.0
    }
    
    # Extract frequency
    freq_match = re.search(r'frequency[:\s]+(\d+(?:\.\d+)?)', command_text, re.IGNORECASE)
    if freq_match:
        parameters["frequency"] = int(float(freq_match.group(1)))
    
    # Extract amplitude  
    amp_match = re.search(r'amplitude[:\s]+(\d+(?:\.\d+)?)', command_text, re.IGNORECASE)
    if amp_match:
        parameters["amplitude"] = float(amp_match.group(1))
    
    # Extract range
    range_match = re.search(r'range[:\s]+(\d+(?:\.\d+)?)[:\s-]+(\d+(?:\.\d+)?)', command_text, re.IGNORECASE)
    if range_match:
        parameters["start_range"] = float(range_match.group(1))
        parameters["end_range"] = float(range_match.group(2))
    
    # Extract phase shift
    phase_match = re.search(r'phase[:\s]*shift[:\s]+(\d+(?:\.\d+)?)', command_text, re.IGNORECASE)
    if phase_match:
        parameters["phase_shift"] = float(phase_match.group(1))
    
    return {"plot_sine_wave": parameters}