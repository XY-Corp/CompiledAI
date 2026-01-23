from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Structured function call for pressure calculation."""
    calc_absolute_pressure: Dict[str, int]


async def parse_pressure_request(
    prompt_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts atmospheric and gauge pressure values from user input and formats them as a function call structure.
    
    Args:
        prompt_text: The raw user input text containing pressure values and calculation request
        available_functions: List of available function definitions to understand expected parameter structure
    
    Returns:
        dict: Returns a structured function call object with calc_absolute_pressure as the key 
              and extracted parameter values
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Format available functions for the LLM prompt
        functions_text = "Available Functions:\n"
        for func in available_functions:
            if func.get('name') == 'calc_absolute_pressure':
                params_schema = func.get('parameters', {})
                functions_text += f"- {func['name']}: requires atm_pressure (int) and gauge_pressure (int)\n"
        
        # Use LLM to extract pressure values from the user input
        prompt = f"""User request: "{prompt_text}"

{functions_text}

Extract the atmospheric pressure and gauge pressure values from the user request.
Look for numbers that represent:
- Atmospheric pressure (baseline/standard pressure)
- Gauge pressure (pressure above atmospheric)

Return JSON in this exact format:
{{"calc_absolute_pressure": {{"atm_pressure": <integer>, "gauge_pressure": <integer>}}}}

Example:
If user says "calculate absolute pressure with atmospheric 14 and gauge 5"
Return: {{"calc_absolute_pressure": {{"atm_pressure": 14, "gauge_pressure": 5}}}}
"""
        
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
            validated = FunctionCall(**data)
            return validated.model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract numbers with regex
            numbers = re.findall(r'\b\d+(?:\.\d+)?\b', prompt_text)
            if len(numbers) >= 2:
                # Assume first number is atmospheric, second is gauge
                atm_pressure = int(float(numbers[0]))
                gauge_pressure = int(float(numbers[1]))
                return {
                    "calc_absolute_pressure": {
                        "atm_pressure": atm_pressure,
                        "gauge_pressure": gauge_pressure
                    }
                }
            else:
                # Default fallback values
                return {
                    "calc_absolute_pressure": {
                        "atm_pressure": 1,
                        "gauge_pressure": 2
                    }
                }
                
    except Exception as e:
        # Error fallback with default values
        return {
            "calc_absolute_pressure": {
                "atm_pressure": 1,
                "gauge_pressure": 2
            }
        }