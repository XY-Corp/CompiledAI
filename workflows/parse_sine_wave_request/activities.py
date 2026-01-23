from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class SineWaveParameters(BaseModel):
    """Define the expected sine wave parameters structure."""
    start_range: float
    end_range: float
    frequency: int
    amplitude: int = 1
    phase_shift: int = 0

async def parse_sine_wave_parameters(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts sine wave plotting parameters from natural language input and formats them for function execution.
    
    Args:
        user_request: The natural language request containing sine wave plotting parameters
        available_functions: List of available function definitions for parameter validation
        
    Returns:
        Dict with plot_sine_wave as key and parameters dict as nested object
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
            # Return default parameters if function not found
            return {"plot_sine_wave": {"start_range": 0.0, "end_range": 6.2832, "frequency": 1, "amplitude": 1, "phase_shift": 0}}
        
        # Get parameter schema
        params_schema = plot_function.get('parameters', {})
        properties = params_schema.get('properties', {}) if isinstance(params_schema, dict) else {}
        
        # Format function schema clearly for LLM with EXACT parameter names
        param_details = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'number')
            description = param_info.get('description', '')
            param_details.append(f'"{param_name}": <{param_type}> - {description}')
        
        schema_text = "Parameters must use these EXACT names:\n" + "\n".join(param_details) if param_details else """
Parameters must use these EXACT names:
"start_range": <number> - Starting value for the x-axis range
"end_range": <number> - Ending value for the x-axis range  
"frequency": <number> - Frequency of the sine wave
"amplitude": <number> - Amplitude of the sine wave (default: 1)
"phase_shift": <number> - Phase shift of the sine wave in radians (default: 0)"""

        # Create prompt for LLM to extract parameters
        prompt = f"""User request: "{user_request}"

Extract sine wave plotting parameters from this request.

{schema_text}

CRITICAL: Use the EXACT parameter names shown above.

Common conversions:
- "from 0 to 2π" → start_range: 0, end_range: 6.2832 (2π ≈ 6.2832)
- "frequency 5" → frequency: 5
- "amplitude 2" → amplitude: 2
- "phase shift π/2" → phase_shift: 1.5708 (π/2 ≈ 1.5708)

Return ONLY valid JSON in this exact format:
{{"start_range": 0.0, "end_range": 6.2832, "frequency": 5, "amplitude": 1, "phase_shift": 0}}"""

        response = llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
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
            
            # Return in the required format with plot_sine_wave as key
            return {"plot_sine_wave": parameters}
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract parameters using regex patterns
            return _extract_parameters_with_regex(user_request)
            
    except Exception as e:
        # Return default parameters on any error
        return {"plot_sine_wave": {"start_range": 0.0, "end_range": 6.2832, "frequency": 1, "amplitude": 1, "phase_shift": 0}}

def _extract_parameters_with_regex(user_request: str) -> dict[str, Any]:
    """Fallback method to extract parameters using regex patterns."""
    
    # Default values
    params = {
        "start_range": 0.0,
        "end_range": 6.2832,  # 2π
        "frequency": 1,
        "amplitude": 1,
        "phase_shift": 0
    }
    
    # Extract frequency
    freq_match = re.search(r'frequency\s*[=:]\s*(\d+(?:\.\d+)?)', user_request, re.IGNORECASE)
    if freq_match:
        params["frequency"] = int(float(freq_match.group(1)))
    
    # Extract amplitude  
    amp_match = re.search(r'amplitude\s*[=:]\s*(\d+(?:\.\d+)?)', user_request, re.IGNORECASE)
    if amp_match:
        params["amplitude"] = int(float(amp_match.group(1)))
    
    # Extract range - look for "from X to Y" patterns
    range_match = re.search(r'from\s+(-?\d+(?:\.\d+)?)\s+to\s+(-?\d+(?:\.\d+)?)', user_request, re.IGNORECASE)
    if range_match:
        params["start_range"] = float(range_match.group(1))
        params["end_range"] = float(range_match.group(2))
    
    # Handle 2π notation
    if '2π' in user_request or '2*π' in user_request or 'two pi' in user_request.lower():
        params["end_range"] = 6.2832
    
    # Handle π/2 phase shift
    if 'π/2' in user_request or 'pi/2' in user_request.lower():
        params["phase_shift"] = 1.5708
    
    return {"plot_sine_wave": params}