from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Define the expected structure for function call extraction."""
    function_name: str
    parameters: Dict[str, Any]

async def extract_function_call_parameters(
    prompt_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse natural language text to extract species, timeframe, and model parameters for evolutionary rate prediction function calls.
    
    Args:
        prompt_text: The complete natural language prompt containing the request for evolutionary rate predictions
        available_functions: List of function definitions that provide context for parameter extraction
        
    Returns:
        Dict in format: {"prediction.evolution": {"species": "Homo Sapiens", "years": 50, "model": "Darwin"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Find the evolutionary prediction function
        target_function = None
        for func in available_functions:
            if "prediction.evolution" in func.get('name', ''):
                target_function = func
                break
        
        if not target_function:
            # Fallback - look for any evolution-related function
            for func in available_functions:
                if 'evolution' in func.get('name', '').lower() or 'evolution' in func.get('description', '').lower():
                    target_function = func
                    break
        
        # Get function name (default to prediction.evolution)
        function_name = target_function.get('name', 'prediction.evolution') if target_function else 'prediction.evolution'
        
        # Create LLM prompt for parameter extraction
        prompt = f"""Extract the species, years, and model parameters from this evolutionary rate prediction request:
"{prompt_text}"

Extract ONLY these parameters:
- species: The species name mentioned (e.g., "Homo Sapiens", "Canis lupus")  
- years: The timeframe in years as an integer
- model: The evolutionary model name (e.g., "Darwin", "Lamarck", "Modern Synthesis")

Return ONLY valid JSON in this exact format:
{{"species": "Species Name", "years": 50, "model": "Model Name"}}

If a parameter is not clearly specified, use reasonable defaults:
- species: "Homo Sapiens" (if not specified)
- years: 100 (if not specified)
- model: "Darwin" (if not specified)"""

        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate the extracted parameters
        try:
            parameters = json.loads(content)
            
            # Validate and normalize parameters
            species = parameters.get('species', 'Homo Sapiens')
            years = int(parameters.get('years', 100))
            model = parameters.get('model', 'Darwin')
            
            # Return in the required format with function name as top-level key
            result = {
                function_name: {
                    "species": species,
                    "years": years,
                    "model": model
                }
            }
            
            return result
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Fallback parsing using regex patterns
            species_match = re.search(r'(?:species|organism)[:,\s]+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)', prompt_text, re.IGNORECASE)
            years_match = re.search(r'(?:years?|time|period)[:,\s]*(\d+)', prompt_text)
            model_match = re.search(r'(?:model|theory)[:,\s]+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)', prompt_text, re.IGNORECASE)
            
            species = species_match.group(1) if species_match else "Homo Sapiens"
            years = int(years_match.group(1)) if years_match else 100
            model = model_match.group(1) if model_match else "Darwin"
            
            result = {
                function_name: {
                    "species": species,
                    "years": years,
                    "model": model
                }
            }
            
            return result
            
    except Exception as e:
        # Return default values on any error
        return {
            "prediction.evolution": {
                "species": "Homo Sapiens",
                "years": 100,
                "model": "Darwin"
            }
        }