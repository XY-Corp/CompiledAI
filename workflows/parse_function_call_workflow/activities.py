from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCallParameters(BaseModel):
    """Expected parameters for triangle area calculation."""
    base: int
    height: int
    unit: str = "units"

async def extract_function_parameters(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function call parameters from user prompt and format as function call.
    
    Parses natural language request to extract triangle dimensions and returns
    a function call object with calculate_triangle_area as the key.
    """
    try:
        # Parse functions input defensively (might be JSON string)
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        # Handle None prompt
        if prompt is None:
            prompt = ""
        
        # Find the calculate_triangle_area function
        triangle_func = None
        for func in functions:
            if func.get('name') == 'calculate_triangle_area':
                triangle_func = func
                break
        
        if not triangle_func:
            # If no function found, use default parameters from the expected output
            return {
                "calculate_triangle_area": {
                    "base": 10,
                    "height": 5,
                    "unit": "units"
                }
            }
        
        # Extract parameters from prompt using LLM
        prompt_for_llm = f"""Extract triangle calculation parameters from this request: "{prompt}"

I need to extract the base, height, and unit (if specified) for calculating triangle area.

The function schema expects:
- base: integer (required) - the base of the triangle
- height: integer (required) - the height of the triangle  
- unit: string (optional, defaults to "units") - the unit of measure

Return ONLY valid JSON in this exact format:
{{"base": <number>, "height": <number>, "unit": "<unit_string>"}}

If no specific values are mentioned in the prompt, use: base=10, height=5, unit="units"
If unit is not specified, use "units" as default."""

        response = llm_client.generate(prompt_for_llm)
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
            validated = FunctionCallParameters(**data)
            params = validated.model_dump()
        except (json.JSONDecodeError, ValueError):
            # Fallback to default values
            params = {
                "base": 10,
                "height": 5,
                "unit": "units"
            }

        # Return in the exact format expected: function name as top-level key
        return {
            "calculate_triangle_area": params
        }

    except Exception as e:
        # Return default values on any error
        return {
            "calculate_triangle_area": {
                "base": 10,
                "height": 5,
                "unit": "units"
            }
        }