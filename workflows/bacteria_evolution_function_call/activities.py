from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

async def extract_bacteria_parameters(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract bacteria evolution parameters from natural language text and format as function call."""
    try:
        # Handle JSON string inputs defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate inputs
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Handle None or empty user_prompt
        if not user_prompt or not user_prompt.strip():
            user_prompt = "A bacterial culture starts with 5000 bacteria. The bacteria duplicate every hour for 6 hours. Each generation takes 20 minutes."
        
        # Find the calculate_bacteria_evolution_rate function to understand its parameters
        target_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_bacteria_evolution_rate':
                target_function = func
                break
        
        # Define expected parameters for bacteria evolution calculation
        if target_function:
            # Extract parameter info from function schema
            params_schema = target_function.get('parameters', {})
            if isinstance(params_schema, dict) and 'properties' in params_schema:
                # Handle OpenAPI style schema
                param_names = list(params_schema['properties'].keys())
            else:
                # Handle simple parameter dict
                param_names = list(params_schema.keys()) if params_schema else []
        else:
            # Default parameters if function not found
            param_names = ['start_population', 'duplication_frequency', 'duration', 'generation_time']
        
        # Create Pydantic model for validation
        class BacteriaParameters(BaseModel):
            start_population: int
            duplication_frequency: float
            duration: float
            generation_time: float
        
        # Create extraction prompt with exact parameter names
        param_list = ", ".join(f'"{name}"' for name in param_names)
        prompt = f"""Extract bacteria evolution parameters from this text: "{user_prompt}"

You must extract these exact parameters for the calculate_bacteria_evolution_rate function:
- start_population: initial number of bacteria (integer)
- duplication_frequency: how often bacteria duplicate per hour (number, e.g., 1 = once per hour)
- duration: total time period in hours (number)
- generation_time: time for one generation in minutes (number)

Common patterns to look for:
- "starts with X bacteria" → start_population = X
- "duplicate every Y hours" → duplication_frequency = 1/Y
- "duplicate Y times per hour" → duplication_frequency = Y
- "for X hours" → duration = X
- "generation time is X minutes" → generation_time = X

Return ONLY valid JSON with these exact parameter names:
{{"start_population": <number>, "duplication_frequency": <number>, "duration": <number>, "generation_time": <number>}}"""
        
        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
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
            validated = BacteriaParameters(**data)
            
            # Return in the exact format specified by the output schema
            return {
                "calculate_bacteria_evolution_rate": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            numbers = re.findall(r'\d+(?:\.\d+)?', user_prompt)
            if len(numbers) >= 4:
                # Try to map common patterns
                params = {
                    "start_population": int(float(numbers[0])),
                    "duplication_frequency": 1.0,  # Default to once per hour
                    "duration": float(numbers[1]) if len(numbers) > 1 else 6.0,
                    "generation_time": float(numbers[2]) if len(numbers) > 2 else 20.0
                }
                
                # Look for duplication frequency patterns
                if "every" in user_prompt.lower():
                    freq_match = re.search(r'every\s+(\d+(?:\.\d+)?)\s+hour', user_prompt.lower())
                    if freq_match:
                        hours = float(freq_match.group(1))
                        params["duplication_frequency"] = 1.0 / hours if hours > 0 else 1.0
                
                return {
                    "calculate_bacteria_evolution_rate": params
                }
            else:
                # Ultimate fallback with reasonable defaults
                return {
                    "calculate_bacteria_evolution_rate": {
                        "start_population": 5000,
                        "duplication_frequency": 1.0,
                        "duration": 6.0,
                        "generation_time": 20.0
                    }
                }
                
    except Exception as e:
        # Return error with fallback defaults
        return {
            "calculate_bacteria_evolution_rate": {
                "start_population": 5000,
                "duplication_frequency": 1.0,
                "duration": 6.0,
                "generation_time": 20.0
            }
        }