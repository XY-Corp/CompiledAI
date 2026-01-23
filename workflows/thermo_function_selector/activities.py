from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class ThermoParameters(BaseModel):
    """Thermodynamics function parameters schema."""
    mass: int
    phase_transition: str  
    substance: str


async def parse_thermo_question(
    question_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes a thermodynamics question to extract mass, phase transition type, and substance for function parameter mapping.
    
    Args:
        question_text: The raw thermodynamics question text containing mass, substance, and phase change information that needs to be parsed
        available_functions: List of available function definitions that provide context for parameter extraction and validation
    
    Returns:
        Dict with thermo.calculate_energy as key and extracted parameters as value
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Create a comprehensive prompt for the LLM to extract thermodynamics parameters
        prompt = f"""Extract thermodynamics parameters from this question: "{question_text}"

You must extract:
1. mass - as an integer (in grams, convert if needed)
2. phase_transition - one of: "melting", "freezing", "vaporization", "condensation"  
3. substance - the material undergoing phase change (default to "water" if not specified)

Examples:
- "100g of water vaporizing" → mass: 100, phase_transition: "vaporization", substance: "water"
- "50 grams of ice melting" → mass: 50, phase_transition: "melting", substance: "water"
- "200g alcohol condensing" → mass: 200, phase_transition: "condensation", substance: "alcohol"

Return ONLY valid JSON in this exact format:
{{"mass": 100, "phase_transition": "vaporization", "substance": "water"}}"""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            # Extract content between ```json and ``` or between ``` and ```
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
            validated = ThermoParameters(**data)
            
            # Return in the exact format required by the schema
            return {
                "thermo.calculate_energy": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            return {"error": f"Failed to parse LLM response as valid JSON: {e}"}
            
    except Exception as e:
        return {"error": f"Failed to process thermodynamics question: {e}"}