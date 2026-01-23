from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class EntropyParameters(BaseModel):
    """Define expected entropy calculation parameters."""
    substance: str = "ice"
    mass: int = 1
    initial_temperature: int = 0
    final_temperature: int = 100
    pressure: int = 1

async def parse_entropy_parameters(
    problem_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract physics problem parameters and format as entropy calculation function call.
    
    Args:
        problem_text: The physics problem text describing entropy calculation scenario
        available_functions: List of available function definitions
    
    Returns:
        Dict with entropy_change.calculate as key and extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Handle empty or None problem_text
        if not problem_text or problem_text.strip() == "":
            return {
                "entropy_change.calculate": {
                    "substance": "ice",
                    "mass": 1,
                    "initial_temperature": 0,
                    "final_temperature": 100,
                    "pressure": 1
                }
            }
        
        # Find the entropy_change.calculate function definition
        entropy_func = None
        for func in available_functions:
            if func.get('name') == 'entropy_change.calculate':
                entropy_func = func
                break
        
        # Get parameter schema (try different possible structures)
        params_schema = {}
        if entropy_func:
            # Try different possible parameter schema locations
            if 'parameters' in entropy_func:
                if isinstance(entropy_func['parameters'], dict) and 'properties' in entropy_func['parameters']:
                    params_schema = entropy_func['parameters']['properties']
                else:
                    params_schema = entropy_func['parameters']
            elif 'params' in entropy_func:
                params_schema = entropy_func['params']
        
        # Format available parameters for LLM prompt
        param_details = []
        for param_name, param_info in params_schema.items():
            if isinstance(param_info, str):
                param_type = param_info
            elif isinstance(param_info, dict):
                param_type = param_info.get('type', 'string')
            else:
                param_type = 'string'
            param_details.append(f'"{param_name}": <{param_type}>')
        
        # Create clean prompt for LLM
        prompt = f"""Extract entropy calculation parameters from this physics problem:

Problem: {problem_text}

Required parameters for entropy_change.calculate:
{', '.join(param_details) if param_details else 'substance, mass, initial_temperature, final_temperature, pressure'}

Extract:
- substance: type of material (e.g., "ice", "water", "steam", "iron")
- mass: amount in kg or g (convert to integer)
- initial_temperature: starting temperature in Celsius (integer)
- final_temperature: ending temperature in Celsius (integer) 
- pressure: pressure in atm or Pa (convert to integer, use 1 if not specified)

Return ONLY valid JSON in this exact format:
{{"substance": "ice", "mass": 1, "initial_temperature": 0, "final_temperature": 100, "pressure": 1}}"""
        
        # Use LLM to extract structured data from physics problem
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
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
            validated = EntropyParameters(**data)
            parameters = validated.model_dump()
            
            # Return in required format with entropy_change.calculate as key
            return {
                "entropy_change.calculate": parameters
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: Try to extract with regex patterns
            fallback_params = extract_entropy_with_regex(problem_text)
            return {
                "entropy_change.calculate": fallback_params
            }
    
    except Exception as e:
        # Return default values if all else fails
        return {
            "entropy_change.calculate": {
                "substance": "ice",
                "mass": 1,
                "initial_temperature": 0,
                "final_temperature": 100,
                "pressure": 1
            }
        }

def extract_entropy_with_regex(text: str) -> dict[str, Any]:
    """Fallback extraction using regex patterns."""
    result = {
        "substance": "ice",
        "mass": 1,
        "initial_temperature": 0,
        "final_temperature": 100,
        "pressure": 1
    }
    
    # Extract substance
    substance_patterns = [
        r'\b(ice|water|steam|iron|copper|aluminum|gold|silver)\b',
        r'\b(H2O|H₂O)\b'
    ]
    for pattern in substance_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            substance = match.group(1).lower()
            if substance in ['h2o', 'h₂o']:
                substance = 'water'
            result["substance"] = substance
            break
    
    # Extract mass (look for numbers followed by mass units)
    mass_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|g|grams?|kilograms?)', text, re.IGNORECASE)
    if mass_match:
        mass_val = float(mass_match.group(1))
        result["mass"] = int(mass_val)
    
    # Extract temperatures
    temp_matches = re.findall(r'(-?\d+(?:\.\d+)?)\s*(?:°C|C|degrees?)', text, re.IGNORECASE)
    if len(temp_matches) >= 2:
        temps = [int(float(t)) for t in temp_matches[:2]]
        result["initial_temperature"] = min(temps)
        result["final_temperature"] = max(temps)
    elif len(temp_matches) == 1:
        temp = int(float(temp_matches[0]))
        if temp < 50:  # Assume it's initial temp
            result["initial_temperature"] = temp
        else:  # Assume it's final temp
            result["final_temperature"] = temp
    
    # Extract pressure
    pressure_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:atm|bar|pa|pascal)', text, re.IGNORECASE)
    if pressure_match:
        result["pressure"] = int(float(pressure_match.group(1)))
    
    return result