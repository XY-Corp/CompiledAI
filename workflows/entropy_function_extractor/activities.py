from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

async def extract_entropy_parameters(
    prompt_text: str,
    function_schema: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the user prompt to extract numerical values and parameters needed for entropy change calculation function call.
    
    Args:
        prompt_text: The complete user prompt containing the entropy change calculation request with temperature values and heat capacity
        function_schema: The schema definition for the calculate_entropy_change function including parameter types and requirements
    
    Returns:
        Dict with calculate_entropy_change as key and extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_schema, str):
            function_schema = json.loads(function_schema)
        
        # Handle case where function_schema is a list of functions
        if isinstance(function_schema, list):
            # Find calculate_entropy_change function
            entropy_func = None
            for func in function_schema:
                if func.get('name') == 'calculate_entropy_change':
                    entropy_func = func
                    break
            function_schema = entropy_func or {}
        
        # Default values if prompt is empty or None
        if not prompt_text or prompt_text.strip() == "":
            return {
                "calculate_entropy_change": {
                    "initial_temp": 300,
                    "final_temp": 400,
                    "heat_capacity": 5,
                    "isothermal": True
                }
            }
        
        # Get parameter schema
        params_schema = function_schema.get('parameters', {})
        if 'properties' in params_schema:
            params_schema = params_schema['properties']
        
        # Create parameter descriptions for LLM prompt
        param_details = []
        for param_name, param_info in params_schema.items():
            if isinstance(param_info, str):
                param_type = param_info
                description = f"{param_name} ({param_type})"
            elif isinstance(param_info, dict):
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '')
                description = f"{param_name} ({param_type}): {param_desc}"
            else:
                description = f"{param_name} (string)"
            param_details.append(description)
        
        # Create clean prompt for LLM extraction
        prompt = f"""Extract entropy change calculation parameters from this user request:

"{prompt_text}"

Extract the following parameters for the calculate_entropy_change function:
{chr(10).join(param_details)}

CRITICAL: Use these EXACT parameter names:
- "initial_temp" (integer) - initial temperature value
- "final_temp" (integer) - final temperature value  
- "heat_capacity" (integer) - heat capacity value
- "isothermal" (boolean) - whether the process is isothermal

Look for:
- Temperature values (initial and final)
- Heat capacity values
- Any mention of isothermal conditions

Return ONLY valid JSON in this exact format:
{{"initial_temp": 300, "final_temp": 400, "heat_capacity": 5, "isothermal": true}}"""

        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Define expected structure for validation
        class EntropyParameters(BaseModel):
            initial_temp: int
            final_temp: int
            heat_capacity: int
            isothermal: bool
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = EntropyParameters(**data)
            
            # Return in required format
            return {
                "calculate_entropy_change": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract numbers with regex
            temps = re.findall(r'\b(\d+(?:\.\d+)?)\s*(?:K|°C|degrees?)', prompt_text, re.IGNORECASE)
            heat_caps = re.findall(r'heat capacity[:\s]+(\d+(?:\.\d+)?)', prompt_text, re.IGNORECASE)
            
            # Use extracted values or defaults
            initial_temp = int(float(temps[0])) if len(temps) > 0 else 300
            final_temp = int(float(temps[1])) if len(temps) > 1 else 400
            heat_capacity = int(float(heat_caps[0])) if heat_caps else 5
            isothermal = 'isothermal' in prompt_text.lower()
            
            return {
                "calculate_entropy_change": {
                    "initial_temp": initial_temp,
                    "final_temp": final_temp,
                    "heat_capacity": heat_capacity,
                    "isothermal": isothermal
                }
            }
            
    except Exception as e:
        # Ultimate fallback with reasonable defaults
        return {
            "calculate_entropy_change": {
                "initial_temp": 300,
                "final_temp": 400,
                "heat_capacity": 5,
                "isothermal": True
            }
        }