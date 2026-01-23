from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class ElectromagneticForceParams(BaseModel):
    """Define the expected electromagnetic force parameters structure."""
    charge1: int
    charge2: int
    distance: int
    medium_permittivity: float = 8.854e-12

async def extract_physics_parameters(
    problem_text: str,
    function_definitions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract electromagnetic force calculation parameters from physics problem text and format as function call.
    
    Args:
        problem_text: The complete physics problem text describing charges, distances, and electromagnetic force calculation requirements
        function_definitions: List of available function definitions with parameter specifications to guide extraction format
    
    Returns:
        Dict with electromagnetic_force as key and extracted parameters: {"electromagnetic_force": {"charge1": 5, "charge2": 7, "distance": 3, "medium_permittivity": 8.854e-12}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_definitions, str):
            function_definitions = json.loads(function_definitions)
        
        # Validate inputs
        if not isinstance(function_definitions, list):
            function_definitions = []
        
        # First try to extract values using regex patterns from the problem text
        charge1_val = 0
        charge2_val = 0
        distance_val = 1
        medium_permittivity_val = 8.854e-12
        
        # Extract charges using regex patterns
        charge_patterns = [
            r'charge[s]?\s*(?:of\s*)?(\d+)(?:\s*[cC]|coulomb)?',
            r'(\d+)\s*[cC](?:oulomb)?',
            r'q[12]?\s*=\s*(\d+)',
            r'(\d+)\s*microcoulomb',
            r'(\d+)(?:\.\d+)?\s*×?\s*10\^?-?\d*\s*[cC]'
        ]
        
        charges_found = []
        for pattern in charge_patterns:
            matches = re.findall(pattern, problem_text, re.IGNORECASE)
            for match in matches:
                try:
                    charge_val = int(float(match))
                    if charge_val not in charges_found:
                        charges_found.append(charge_val)
                except ValueError:
                    continue
        
        # Assign charges if found
        if len(charges_found) >= 2:
            charge1_val = charges_found[0]
            charge2_val = charges_found[1]
        elif len(charges_found) == 1:
            charge1_val = charges_found[0]
            charge2_val = charges_found[0]
        
        # Extract distance using regex patterns
        distance_patterns = [
            r'distance[s]?\s*(?:of\s*)?(\d+)(?:\s*[mM]|meter|metre)?',
            r'(\d+)\s*[mM](?:eter|etre)?',
            r'apart[s]?\s*(?:by\s*)?(\d+)',
            r'separated\s*(?:by\s*)?(\d+)',
            r'r\s*=\s*(\d+)',
            r'(\d+)\s*(?:cm|centimeter)'
        ]
        
        for pattern in distance_patterns:
            match = re.search(pattern, problem_text, re.IGNORECASE)
            if match:
                try:
                    distance_val = int(float(match.group(1)))
                    break
                except ValueError:
                    continue
        
        # Extract medium permittivity if mentioned
        permittivity_patterns = [
            r'permittivity[s]?\s*(?:of\s*)?([0-9.]+(?:[eE]-?\d+)?)',
            r'ε[r0]?\s*=\s*([0-9.]+(?:[eE]-?\d+)?)',
            r'dielectric[s]?\s*(?:constant\s*)?([0-9.]+)',
            r'vacuum\s*permittivity',
            r'free\s*space'
        ]
        
        for pattern in permittivity_patterns:
            match = re.search(pattern, problem_text, re.IGNORECASE)
            if match:
                if 'vacuum' in match.group(0).lower() or 'free space' in match.group(0).lower():
                    medium_permittivity_val = 8.854e-12
                    break
                else:
                    try:
                        medium_permittivity_val = float(match.group(1))
                        break
                    except (ValueError, IndexError):
                        continue
        
        # If regex extraction didn't find enough values, use LLM as fallback
        if charge1_val == 0 and charge2_val == 0 and distance_val == 1:
            # Create clean prompt for LLM
            prompt = f"""Extract electromagnetic force calculation parameters from this physics problem:

{problem_text}

Return ONLY valid JSON in this exact format:
{{"charge1": 5, "charge2": 7, "distance": 3, "medium_permittivity": 8.854e-12}}

Where:
- charge1, charge2: integer values representing charge magnitudes in coulombs
- distance: integer value in meters  
- medium_permittivity: float value (use 8.854e-12 if not specified)"""

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
                validated = ElectromagneticForceParams(**llm_data)
                llm_params = validated.model_dump()
                
                # Use LLM extracted values
                charge1_val = llm_params.get('charge1', charge1_val)
                charge2_val = llm_params.get('charge2', charge2_val) 
                distance_val = llm_params.get('distance', distance_val)
                medium_permittivity_val = llm_params.get('medium_permittivity', medium_permittivity_val)
                
            except (json.JSONDecodeError, ValueError):
                # Keep the regex-extracted or default values
                pass
        
        # Ensure we have reasonable defaults if everything failed
        if charge1_val <= 0:
            charge1_val = 1
        if charge2_val <= 0:
            charge2_val = 1
        if distance_val <= 0:
            distance_val = 1
            
        # Return in the exact format specified by the output schema
        return {
            "electromagnetic_force": {
                "charge1": charge1_val,
                "charge2": charge2_val,
                "distance": distance_val,
                "medium_permittivity": medium_permittivity_val
            }
        }
        
    except json.JSONDecodeError as e:
        # Return default structure on JSON parse error
        return {
            "electromagnetic_force": {
                "charge1": 1,
                "charge2": 1,
                "distance": 1,
                "medium_permittivity": 8.854e-12
            }
        }
    except Exception as e:
        # Return default structure on any other error
        return {
            "electromagnetic_force": {
                "charge1": 1,
                "charge2": 1,
                "distance": 1,
                "medium_permittivity": 8.854e-12
            }
        }