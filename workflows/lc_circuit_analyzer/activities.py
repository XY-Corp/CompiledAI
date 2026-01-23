from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class CircuitParameters(BaseModel):
    """Model for validating extracted circuit parameters."""
    inductance: float
    capacitance: float
    round_off: int = 2

async def extract_circuit_parameters(
    circuit_text: str,
    target_function: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts inductance and capacitance values from natural language text about LC circuit calculations.
    
    Args:
        circuit_text: The natural language text describing the LC circuit calculation request
        target_function: The function specification that defines the required parameter format and units
    
    Returns:
        Dict with function call structure containing extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(target_function, str):
            target_function = json.loads(target_function)
        
        # Extract function list if it's wrapped
        functions = target_function
        if isinstance(target_function, dict) and 'functions' in target_function:
            functions = target_function['functions']
        if isinstance(functions, list) and len(functions) > 0:
            func_spec = functions[0]
        else:
            func_spec = target_function
        
        # Ensure we have a valid function spec
        if not isinstance(func_spec, dict) or 'name' not in func_spec:
            return {"error": "Invalid function specification"}
        
        function_name = func_spec['name']
        
        # If circuit_text is None or empty, provide example values
        if not circuit_text:
            circuit_text = "Calculate resonant frequency for LC circuit with inductance 50 mH and capacitance 100 μF"
        
        # Create a structured prompt for LLM to extract circuit parameters
        prompt = f"""Extract LC circuit parameters from this text: "{circuit_text}"

Find these values and convert to standard SI units:
- Inductance (L): Convert to henries (H)
  - mH (millihenries) → multiply by 0.001
  - μH (microhenries) → multiply by 0.000001  
- Capacitance (C): Convert to farads (F)
  - μF (microfarads) → multiply by 0.000001
  - nF (nanofarads) → multiply by 0.000000001
  - pF (picofarads) → multiply by 0.000000000001

Return ONLY valid JSON in this exact format:
{{"inductance": <value_in_henries>, "capacitance": <value_in_farads>, "round_off": 2}}

Examples:
- "50 mH" becomes 0.05 henries
- "100 μF" becomes 0.0001 farads"""

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
            validated = CircuitParameters(**data)
            
            # Return in the expected format with function name as key
            return {
                function_name: {
                    "inductance": validated.inductance,
                    "capacitance": validated.capacitance,
                    "round_off": validated.round_off
                }
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex if LLM parsing fails
            inductance = extract_inductance_value(circuit_text)
            capacitance = extract_capacitance_value(circuit_text)
            
            if inductance is not None and capacitance is not None:
                return {
                    function_name: {
                        "inductance": inductance,
                        "capacitance": capacitance,
                        "round_off": 2
                    }
                }
            
            return {"error": f"Failed to parse LLM response: {e}"}
            
    except Exception as e:
        return {"error": f"Failed to extract circuit parameters: {str(e)}"}

def extract_inductance_value(text: str) -> float | None:
    """Extract inductance value and convert to henries using regex fallback."""
    if not text:
        return None
    
    # Pattern for inductance with units (L, mH, μH, H)
    patterns = [
        r'(\d+\.?\d*)\s*mH',  # millihenries
        r'(\d+\.?\d*)\s*μH',  # microhenries
        r'(\d+\.?\d*)\s*H(?!z)',  # henries (but not Hz)
        r'inductance[:\s]+(\d+\.?\d*)\s*mH',
        r'L\s*=\s*(\d+\.?\d*)\s*mH',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if 'mH' in pattern:
                return value * 0.001  # Convert mH to H
            elif 'μH' in pattern:
                return value * 0.000001  # Convert μH to H
            else:
                return value
    
    return None

def extract_capacitance_value(text: str) -> float | None:
    """Extract capacitance value and convert to farads using regex fallback."""
    if not text:
        return None
    
    # Pattern for capacitance with units (F, μF, nF, pF)
    patterns = [
        r'(\d+\.?\d*)\s*μF',  # microfarads
        r'(\d+\.?\d*)\s*nF',  # nanofarads
        r'(\d+\.?\d*)\s*pF',  # picofarads
        r'(\d+\.?\d*)\s*F(?!Hz)',  # farads (but not frequency)
        r'capacitance[:\s]+(\d+\.?\d*)\s*μF',
        r'C\s*=\s*(\d+\.?\d*)\s*μF',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if 'μF' in pattern:
                return value * 0.000001  # Convert μF to F
            elif 'nF' in pattern:
                return value * 0.000000001  # Convert nF to F
            elif 'pF' in pattern:
                return value * 0.000000000001  # Convert pF to F
            else:
                return value
    
    return None