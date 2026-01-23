from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class EvolutionParameters(BaseModel):
    """Structure for extracted evolution prediction parameters."""
    species: str
    years: int
    model: str

async def extract_evolution_parameters(
    user_prompt: str,
    function_definitions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract species, timeframe, and model parameters from natural language prompt for evolution prediction function call.
    
    Args:
        user_prompt: The natural language query containing the evolution prediction request with species name, time period, and optional model specification
        function_definitions: List of available function definitions to understand the required parameter structure and constraints
        
    Returns:
        Dict containing prediction.evolution key with extracted parameters (species, years, model) as nested values.
        Example: {"prediction.evolution": {"species": "Homo Sapiens", "years": 50, "model": "Darwin"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_definitions, str):
            function_definitions = json.loads(function_definitions)
        
        # Find the evolution prediction function for parameter validation
        target_function = None
        for func in function_definitions:
            if "prediction.evolution" in func.get('name', ''):
                target_function = func
                break
        
        if not target_function:
            # Fallback - look for any evolution-related function
            for func in function_definitions:
                if 'evolution' in func.get('name', '').lower() or 'evolution' in func.get('description', '').lower():
                    target_function = func
                    break
        
        # Create LLM prompt for parameter extraction
        prompt = f"""Extract evolution prediction parameters from this request: "{user_prompt}"

Return JSON with these exact parameters:
- species: The species name (as a string)
- years: Time period for prediction (as a number)  
- model: Evolution model to use (as a string, default to "Darwin" if not specified)

Return ONLY valid JSON in this format:
{{"species": "Species Name", "years": 100, "model": "Darwin"}}"""

        response = llm_client.generate(prompt)
        
        # Extract JSON from response (handle markdown code blocks)
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
        try:
            data = json.loads(content)
            validated = EvolutionParameters(**data)
            
            # Return in the required format
            return {
                "prediction.evolution": validated.model_dump()
            }
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: Try to extract using regex patterns
            species_match = re.search(r'(?:species|for)\s+([A-Za-z\s]+?)(?:\s+(?:over|for|in)|$)', user_prompt, re.IGNORECASE)
            years_match = re.search(r'(\d+)\s*(?:years?|decades?|centuries?)', user_prompt, re.IGNORECASE)
            model_match = re.search(r'(?:using|with|model)\s+([A-Za-z]+)', user_prompt, re.IGNORECASE)
            
            species = species_match.group(1).strip() if species_match else "Unknown Species"
            
            # Handle years conversion
            years = 100  # default
            if years_match:
                num = int(years_match.group(1))
                if 'decade' in user_prompt.lower():
                    years = num * 10
                elif 'centur' in user_prompt.lower():
                    years = num * 100
                else:
                    years = num
            
            model = model_match.group(1).strip() if model_match else "Darwin"
            
            return {
                "prediction.evolution": {
                    "species": species,
                    "years": years,
                    "model": model
                }
            }
            
    except Exception as e:
        # Return default structure with error indication
        return {
            "prediction.evolution": {
                "species": "Unknown Species",
                "years": 100,
                "model": "Darwin"
            }
        }