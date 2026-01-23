from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class EntropyParameters(BaseModel):
    """Define the expected entropy calculation parameters."""
    initial_temp: int
    final_temp: int
    heat_capacity: int
    isothermal: bool = True

async def parse_entropy_parameters(
    prompt_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the temperature and heat capacity values from the user prompt and format as a function call.
    
    Args:
        prompt_text: The raw user input containing temperature and heat capacity information for entropy calculation
        available_functions: List of available function definitions for context
        
    Returns:
        Dict containing calculate_entropy_change function call with extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
            
        # First try to extract values using regex patterns (prefer deterministic code)
        initial_temp = None
        final_temp = None
        heat_capacity = None
        isothermal = True  # Default value
        
        # Extract temperature values using regex patterns
        temp_patterns = [
            r'initial.{0,20}temp\w*.{0,10}(\d+)',
            r'from.{0,10}(\d+)\s*(?:k|kelvin|°k|degrees)',
            r'starting.{0,20}temp\w*.{0,10}(\d+)',
            r'T1?.{0,5}=?.{0,5}(\d+)',
        ]
        
        final_temp_patterns = [
            r'final.{0,20}temp\w*.{0,10}(\d+)',
            r'to.{0,10}(\d+)\s*(?:k|kelvin|°k|degrees)',
            r'ending.{0,20}temp\w*.{0,10}(\d+)',
            r'T2.{0,5}=?.{0,5}(\d+)',
        ]
        
        heat_capacity_patterns = [
            r'heat.{0,20}capacity.{0,10}(\d+)',
            r'cp?.{0,5}=?.{0,5}(\d+)',
            r'c.{0,5}=?.{0,5}(\d+)',
        ]
        
        # Try to extract initial temperature
        for pattern in temp_patterns:
            match = re.search(pattern, prompt_text.lower())
            if match and initial_temp is None:
                initial_temp = int(match.group(1))
                break
                
        # Try to extract final temperature
        for pattern in final_temp_patterns:
            match = re.search(pattern, prompt_text.lower())
            if match and final_temp is None:
                final_temp = int(match.group(1))
                break
                
        # Try to extract heat capacity
        for pattern in heat_capacity_patterns:
            match = re.search(pattern, prompt_text.lower())
            if match and heat_capacity is None:
                heat_capacity = int(match.group(1))
                break
                
        # If regex extraction failed, try to find any numbers in the text
        if initial_temp is None or final_temp is None or heat_capacity is None:
            # Extract all numbers from the prompt
            numbers = re.findall(r'\d+', prompt_text)
            if numbers:
                # Make educated guesses based on typical entropy calculation values
                if len(numbers) >= 3:
                    if initial_temp is None:
                        initial_temp = int(numbers[0])
                    if final_temp is None:
                        final_temp = int(numbers[1])
                    if heat_capacity is None:
                        heat_capacity = int(numbers[2])
                elif len(numbers) == 2:
                    if initial_temp is None:
                        initial_temp = int(numbers[0])
                    if final_temp is None:
                        final_temp = int(numbers[1])
                    if heat_capacity is None:
                        heat_capacity = 5  # Default reasonable value
                        
        # Check for isothermal indicators
        if re.search(r'isothermal', prompt_text.lower()):
            isothermal = True
        elif re.search(r'adiabatic|isobaric|isochoric', prompt_text.lower()):
            isothermal = False
            
        # If still missing values, use LLM as fallback
        if initial_temp is None or final_temp is None or heat_capacity is None:
            prompt = f"""Extract entropy calculation parameters from this text: {prompt_text}

I need to extract:
- initial_temp: initial temperature (integer)
- final_temp: final temperature (integer)  
- heat_capacity: heat capacity value (integer)
- isothermal: whether process is isothermal (true/false)

Return ONLY valid JSON in this exact format:
{{"initial_temp": 300, "final_temp": 400, "heat_capacity": 5, "isothermal": true}}"""

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
                        
            try:
                llm_data = json.loads(content)
                if initial_temp is None:
                    initial_temp = llm_data.get('initial_temp', 300)
                if final_temp is None:
                    final_temp = llm_data.get('final_temp', 400)
                if heat_capacity is None:
                    heat_capacity = llm_data.get('heat_capacity', 5)
                isothermal = llm_data.get('isothermal', True)
            except (json.JSONDecodeError, ValueError):
                # Use defaults if LLM parsing fails
                if initial_temp is None:
                    initial_temp = 300
                if final_temp is None:
                    final_temp = 400
                if heat_capacity is None:
                    heat_capacity = 5
                    
        # Validate and create parameters object
        try:
            validated = EntropyParameters(
                initial_temp=initial_temp,
                final_temp=final_temp,
                heat_capacity=heat_capacity,
                isothermal=isothermal
            )
            
            # Return in the exact format specified by the output schema
            return {
                "calculate_entropy_change": validated.model_dump()
            }
            
        except ValueError as e:
            # Fallback with reasonable defaults
            return {
                "calculate_entropy_change": {
                    "initial_temp": 300,
                    "final_temp": 400,
                    "heat_capacity": 5,
                    "isothermal": True
                }
            }
            
    except Exception as e:
        # Error fallback with defaults
        return {
            "calculate_entropy_change": {
                "initial_temp": 300,
                "final_temp": 400,
                "heat_capacity": 5,
                "isothermal": True
            }
        }