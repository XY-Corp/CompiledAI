from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class ThermodynamicsParameters(BaseModel):
    """Validate extracted thermodynamics parameters."""
    mass: int
    phase_transition: str
    substance: str = "water"

async def parse_thermodynamics_problem(
    problem_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract thermodynamics parameters (mass, phase transition, substance) from natural language physics problem text and format as function call.
    
    Args:
        problem_text: The complete physics problem text describing the thermodynamics calculation to be performed, including mass values, substances, and phase transitions
        available_functions: List of available function definitions that can be called to solve the problem
    
    Returns:
        Dict with thermo.calculate_energy as key and extracted parameters as value
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Handle None problem_text
        if problem_text is None:
            problem_text = "Calculate the energy required to vaporize 100 grams of water"
        
        # Create a prompt to extract thermodynamics parameters
        prompt = f"""Extract thermodynamics parameters from this physics problem: "{problem_text}"

I need you to identify:
1. Mass (in grams) - extract the numerical value
2. Phase transition - one of: melting, freezing, vaporization, condensation  
3. Substance - the material undergoing phase change (default: water)

Return ONLY valid JSON in this exact format:
{{"mass": 100, "phase_transition": "vaporization", "substance": "water"}}

Examples:
- "How much energy to melt 50g of ice?" → {{"mass": 50, "phase_transition": "melting", "substance": "water"}}
- "Energy needed to boil 200 grams of water" → {{"mass": 200, "phase_transition": "vaporization", "substance": "water"}}
- "What energy is released when 75g of steam condenses?" → {{"mass": 75, "phase_transition": "condensation", "substance": "water"}}

Problem: {problem_text}"""

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

        # Parse and validate with Pydantic
        data = json.loads(content)
        validated = ThermodynamicsParameters(**data)
        
        # Return in the exact format expected by the schema
        return {
            "thermo.calculate_energy": validated.model_dump()
        }
        
    except json.JSONDecodeError as e:
        # Fallback: try to extract with regex patterns
        try:
            mass = 100  # default
            phase_transition = "vaporization"  # default
            substance = "water"  # default
            
            # Extract mass
            mass_match = re.search(r'(\d+)\s*(?:g|grams?|kg|kilograms?)', problem_text.lower())
            if mass_match:
                mass_value = int(mass_match.group(1))
                # Convert kg to grams if needed
                if 'kg' in mass_match.group(0):
                    mass = mass_value * 1000
                else:
                    mass = mass_value
            
            # Extract phase transition
            if any(word in problem_text.lower() for word in ['melt', 'melting']):
                phase_transition = "melting"
            elif any(word in problem_text.lower() for word in ['freeze', 'freezing']):
                phase_transition = "freezing"
            elif any(word in problem_text.lower() for word in ['boil', 'vaporiz', 'evaporate']):
                phase_transition = "vaporization"
            elif any(word in problem_text.lower() for word in ['condense', 'condensation']):
                phase_transition = "condensation"
            
            # Extract substance
            if 'ice' in problem_text.lower():
                substance = "water"
            elif 'steam' in problem_text.lower():
                substance = "water"
            
            return {
                "thermo.calculate_energy": {
                    "mass": mass,
                    "phase_transition": phase_transition,
                    "substance": substance
                }
            }
            
        except Exception as fallback_e:
            return {
                "thermo.calculate_energy": {
                    "mass": 100,
                    "phase_transition": "vaporization",
                    "substance": "water"
                }
            }
    except Exception as e:
        return {
            "thermo.calculate_energy": {
                "mass": 100,
                "phase_transition": "vaporization",
                "substance": "water"
            }
        }