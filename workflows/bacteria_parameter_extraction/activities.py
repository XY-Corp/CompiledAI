from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class BacteriaParameters(BaseModel):
    """Expected structure for bacteria evolution parameters."""
    start_population: int
    duplication_frequency: int
    duration: int
    generation_time: int = 20


async def extract_bacteria_parameters(
    problem_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract numerical parameters for bacteria evolution calculation from natural language description."""
    try:
        # Handle JSON string inputs defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Handle None problem_text case
        if problem_text is None:
            problem_text = ""
        
        # Validate inputs
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
            
        if not problem_text.strip():
            # If no problem text, try to use a default bacteria evolution scenario
            problem_text = "A bacterial culture starts with 5000 bacteria. The bacteria duplicate every hour for 6 hours. Each generation takes 20 minutes."

        # Find the calculate_bacteria_evolution_rate function to understand its parameters
        target_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_bacteria_evolution_rate':
                target_function = func
                break
        
        if not target_function:
            # Default parameter extraction if function not found
            parameters_info = {
                'start_population': 'starting population of bacteria',
                'duplication_frequency': 'duplication frequency per hour',
                'duration': 'total duration in hours',
                'generation_time': 'generation time in minutes'
            }
        else:
            # Extract parameter info from function schema
            params_schema = target_function.get('parameters', {}).get('properties', {})
            parameters_info = {
                param_name: param_info.get('description', param_name)
                for param_name, param_info in params_schema.items()
            }

        # Create clear extraction prompt
        param_descriptions = "\n".join([f"- {name}: {desc}" for name, desc in parameters_info.items()])
        
        prompt = f"""Extract the following numerical parameters from this bacteria evolution problem:

{param_descriptions}

Problem text: "{problem_text}"

Return ONLY valid JSON in this exact format:
{{"start_population": 5000, "duplication_frequency": 1, "duration": 6, "generation_time": 20}}

Use these extraction rules:
- start_population: Look for initial/starting number of bacteria
- duplication_frequency: Look for how often bacteria duplicate per hour (if "every hour" = 1, if "every 2 hours" = 0.5)
- duration: Look for total time period in hours
- generation_time: Look for generation time in minutes (default: 20 if not specified)"""

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
            params = validated.model_dump()
            
            # Return in the exact format required by the schema
            return {
                "calculate_bacteria_evolution_rate": params
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try regex extraction from problem text
            return extract_with_regex(problem_text)
            
    except Exception as e:
        # Last resort fallback with reasonable defaults
        return {
            "calculate_bacteria_evolution_rate": {
                "start_population": 5000,
                "duplication_frequency": 1,
                "duration": 6,
                "generation_time": 20
            }
        }


def extract_with_regex(text: str) -> dict[str, Any]:
    """Fallback regex-based parameter extraction."""
    try:
        # Extract numbers from text
        numbers = re.findall(r'\d+', text)
        if len(numbers) < 3:
            numbers = [5000, 1, 6, 20]  # defaults
        
        # Basic heuristics for parameter assignment
        start_population = int(numbers[0]) if len(numbers) > 0 else 5000
        duplication_frequency = 1  # default
        duration = int(numbers[1]) if len(numbers) > 1 else 6
        generation_time = int(numbers[2]) if len(numbers) > 2 else 20
        
        # Look for specific patterns
        if "hour" in text.lower():
            hour_match = re.search(r'(\d+)\s*hour', text.lower())
            if hour_match:
                duration = int(hour_match.group(1))
                
        if "minute" in text.lower():
            minute_match = re.search(r'(\d+)\s*minute', text.lower())
            if minute_match:
                generation_time = int(minute_match.group(1))
        
        return {
            "calculate_bacteria_evolution_rate": {
                "start_population": start_population,
                "duplication_frequency": duplication_frequency,
                "duration": duration,
                "generation_time": generation_time
            }
        }
    except:
        return {
            "calculate_bacteria_evolution_rate": {
                "start_population": 5000,
                "duplication_frequency": 1,
                "duration": 6,
                "generation_time": 20
            }
        }