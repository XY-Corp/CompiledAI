from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class HeatCapacityParams(BaseModel):
    """Validated heat capacity parameters."""
    temp: int
    volume: int  
    gas: str = "air"


async def extract_heat_capacity_parameters(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract temperature and volume values from the user prompt and map them to calc_heat_capacity function parameters.
    
    Args:
        prompt: The user's question containing temperature and volume information for heat capacity calculation
        functions: List of available function definitions for context and validation
        
    Returns:
        Dict with calc_heat_capacity key containing temp (integer), volume (integer), and gas (string) parameters
    """
    try:
        # Parse JSON string if needed for functions
        if isinstance(functions, str):
            functions = json.loads(functions)
            
        # First try regex patterns for common formats
        # Temperature patterns: "25°C", "298K", "25 degrees", "25 celsius", etc.
        temp_patterns = [
            r'(\d+)°?C\b',  # 25°C or 25C
            r'(\d+)°?\s*celsius',  # 25 celsius
            r'(\d+)\s*degrees?\s*celsius',  # 25 degrees celsius
            r'(\d+)°?K\b',  # 298K
            r'(\d+)°?\s*kelvin',  # 298 kelvin
            r'(\d+)\s*degrees?\s*kelvin',  # 298 degrees kelvin
            r'temperature[:\s=]+(\d+)',  # temperature: 25
            r'temp[:\s=]+(\d+)',  # temp: 25
        ]
        
        # Volume patterns: "10 m³", "10 cubic meters", "10L", etc.
        volume_patterns = [
            r'(\d+)\s*m[³3]',  # 10 m³ or 10 m3
            r'(\d+)\s*cubic\s*meters?',  # 10 cubic meters
            r'(\d+)\s*L\b',  # 10L
            r'(\d+)\s*liters?',  # 10 liters
            r'volume[:\s=]+(\d+)',  # volume: 10
            r'vol[:\s=]+(\d+)',  # vol: 10
        ]
        
        # Extract temperature
        temperature = None
        temp_celsius = False
        
        for pattern in temp_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                temperature = int(match.group(1))
                # Check if it's Celsius (need to convert to Kelvin)
                if any(unit in pattern.lower() for unit in ['c', 'celsius']):
                    temp_celsius = True
                break
        
        # Convert Celsius to Kelvin if needed
        if temperature is not None and temp_celsius:
            temperature = temperature + 273  # Convert C to K
            
        # Extract volume  
        volume = None
        
        for pattern in volume_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                volume = int(match.group(1))
                # Convert liters to cubic meters if needed
                if 'l' in pattern.lower() or 'liter' in pattern.lower():
                    volume = volume // 1000  # Convert L to m³ (rough conversion)
                break
        
        # If regex didn't work, use LLM as fallback
        if temperature is None or volume is None:
            # Build context about the calc_heat_capacity function
            func_context = ""
            for func in functions:
                if func.get('name') == 'calc_heat_capacity':
                    params_info = func.get('parameters', func.get('params', {}))
                    func_context = f"Function: {func['name']}\nDescription: {func.get('description', '')}\n"
                    func_context += "Required parameters:\n"
                    for param_name, param_info in params_info.items():
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'string')
                            param_desc = param_info.get('description', '')
                        else:
                            param_type = str(param_info)
                            param_desc = ''
                        func_context += f"- {param_name}: {param_type} - {param_desc}\n"
                    break
            
            llm_prompt = f"""Extract temperature and volume parameters from this request: "{prompt}"

{func_context}

CRITICAL REQUIREMENTS:
- Temperature must be in Kelvin (convert from Celsius if needed: K = C + 273)
- Volume must be in cubic meters (m³)
- Gas defaults to "air"

Return ONLY valid JSON in this exact format:
{{"temp": <integer_kelvin>, "volume": <integer_m3>, "gas": "air"}}

Examples:
- "25°C and 10 m³" → {{"temp": 298, "volume": 10, "gas": "air"}}
- "300K and 5 cubic meters" → {{"temp": 300, "volume": 5, "gas": "air"}}"""

            response = llm_client.generate(llm_prompt)
            content = response.content.strip()
            
            # Extract JSON from response 
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
                validated = HeatCapacityParams(**data)
                return {"calc_heat_capacity": validated.model_dump()}
            except (json.JSONDecodeError, ValueError) as e:
                # Use any values we did extract, fill defaults for missing
                temperature = temperature or 298  # Default room temperature in K
                volume = volume or 1  # Default 1 m³
        
        # Use extracted or default values
        if temperature is None:
            temperature = 298  # Default room temperature in Kelvin
        if volume is None:
            volume = 1  # Default 1 cubic meter
            
        # Validate and return result
        validated = HeatCapacityParams(temp=temperature, volume=volume, gas="air")
        return {"calc_heat_capacity": validated.model_dump()}
        
    except Exception as e:
        # Return reasonable defaults on any error
        return {"calc_heat_capacity": {"temp": 298, "volume": 1, "gas": "air"}}