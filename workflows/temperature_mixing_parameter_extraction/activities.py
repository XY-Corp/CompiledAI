from typing import Any, Dict, List, Optional
import re
import json

async def extract_temperature_mixing_parameters(
    prompt_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts numerical parameters (masses and temperatures) from the input prompt text using regex patterns and formats them as function call parameters.
    
    Args:
        prompt_text: The raw input text containing temperature mixing calculation request with numerical values for masses (in kg) and temperatures (in Celsius)
        available_functions: List of available function definitions to understand the expected parameter structure and requirements
    
    Returns:
        Dict with 'calculate_final_temperature' key containing extracted parameters
    """
    # Handle case where prompt_text might be None
    if not prompt_text:
        return {"calculate_final_temperature": {}}
    
    # Handle JSON string input for available_functions
    if isinstance(available_functions, str):
        try:
            available_functions = json.loads(available_functions)
        except json.JSONDecodeError:
            available_functions = []
    
    # Extract masses using regex patterns
    # Look for patterns like "20 kg", "15kg", "mass of 20", etc.
    mass_patterns = [
        r'(\d+(?:\.\d+)?)\s*kg',  # "20 kg" or "20.5 kg"
        r'mass.*?(\d+(?:\.\d+)?)',  # "mass of 20" or "mass is 15.5"
        r'(\d+(?:\.\d+)?)\s*kilogram',  # "20 kilogram"
        r'm[12]?\s*=?\s*(\d+(?:\.\d+)?)'  # "m1 = 20" or "m = 15"
    ]
    
    masses = []
    for pattern in mass_patterns:
        matches = re.findall(pattern, prompt_text, re.IGNORECASE)
        for match in matches:
            try:
                masses.append(float(match))
            except ValueError:
                continue
    
    # Extract temperatures using regex patterns
    # Look for patterns like "30°C", "60 degrees", "temperature of 45", etc.
    temp_patterns = [
        r'(\d+(?:\.\d+)?)\s*°?[Cc]',  # "30°C" or "60 C"
        r'(\d+(?:\.\d+)?)\s*degrees?',  # "30 degrees"
        r'temperature.*?(\d+(?:\.\d+)?)',  # "temperature of 30"
        r'[Tt][12]?\s*=?\s*(\d+(?:\.\d+)?)'  # "T1 = 30" or "t = 60"
    ]
    
    temperatures = []
    for pattern in temp_patterns:
        matches = re.findall(pattern, prompt_text, re.IGNORECASE)
        for match in matches:
            try:
                temperatures.append(float(match))
            except ValueError:
                continue
    
    # Remove duplicates while preserving order
    masses = list(dict.fromkeys(masses))
    temperatures = list(dict.fromkeys(temperatures))
    
    # Build the result with extracted parameters
    result = {"calculate_final_temperature": {}}
    
    # Assign masses (take first two if available)
    if len(masses) >= 1:
        result["calculate_final_temperature"]["mass1"] = masses[0]
    if len(masses) >= 2:
        result["calculate_final_temperature"]["mass2"] = masses[1]
    
    # Assign temperatures (take first two if available)
    if len(temperatures) >= 1:
        result["calculate_final_temperature"]["temperature1"] = temperatures[0]
    if len(temperatures) >= 2:
        result["calculate_final_temperature"]["temperature2"] = temperatures[1]
    
    # Add specific heat capacity if mentioned, otherwise use default for water
    specific_heat_pattern = r'specific\s+heat.*?(\d+(?:\.\d+)?)'
    specific_heat_match = re.search(specific_heat_pattern, prompt_text, re.IGNORECASE)
    if specific_heat_match:
        result["calculate_final_temperature"]["specific_heat_capacity"] = float(specific_heat_match.group(1))
    elif "water" in prompt_text.lower():
        # Default specific heat capacity for water
        result["calculate_final_temperature"]["specific_heat_capacity"] = 4.2
    
    return result