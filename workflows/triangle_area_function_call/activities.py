from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class TriangleFunction(BaseModel):
    """Expected structure for triangle area calculation function call."""
    base: int
    height: int
    unit: str

async def parse_triangle_request(
    prompt_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse natural language request to extract triangle dimensions and generate function call structure.
    
    Args:
        prompt_text: The natural language request containing triangle base and height measurements
        
    Returns:
        Dict with 'calculate_area' key containing base, height, and unit parameters
    """
    try:
        # Use LLM to extract triangle parameters from natural language
        llm_prompt = f"""Extract triangle dimensions from this natural language request:

"{prompt_text}"

Find the base and height measurements and their unit. Return ONLY valid JSON in this exact format:
{{"base": 6, "height": 10, "unit": "cm"}}

Where:
- base: integer value for triangle base
- height: integer value for triangle height  
- unit: string for measurement unit (cm, m, inches, etc.)

If units are not specified, use "units" as default."""

        response = llm_client.generate(llm_prompt)
        
        # Extract JSON from response (handles markdown code blocks)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
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
        data = json.loads(content)
        validated = TriangleFunction(**data)
        
        # Return in the exact format specified by the output schema
        return {
            "calculate_area": validated.model_dump()
        }
        
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback: try to extract with regex patterns
        try:
            # Look for number patterns in the text
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\s*(cm|m|mm|inch|inches|ft|feet|units?)?\b', prompt_text.lower())
            
            if len(numbers) >= 2:
                base = int(float(numbers[0][0]))
                height = int(float(numbers[1][0]))
                
                # Determine unit
                unit = "units"
                for _, found_unit in numbers:
                    if found_unit:
                        unit = found_unit
                        break
                
                return {
                    "calculate_area": {
                        "base": base,
                        "height": height,
                        "unit": unit
                    }
                }
            else:
                # Default fallback values
                return {
                    "calculate_area": {
                        "base": 1,
                        "height": 1,
                        "unit": "units"
                    }
                }
                
        except Exception:
            # Ultimate fallback
            return {
                "calculate_area": {
                    "base": 1,
                    "height": 1,
                    "unit": "units"
                }
            }