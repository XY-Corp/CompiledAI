from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Expected structure for genetics.calculate_similarity function call."""
    species1: str
    species2: str
    format: str = "percentage"


async def parse_genetics_query(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user query to extract species names and determine the appropriate function call structure for genetic similarity calculation.
    
    Args:
        query_text: The raw user query text asking about genetic similarity between species
        available_functions: List of available function definitions to understand expected parameter structure
        
    Returns:
        Dict with genetics.calculate_similarity key containing function parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate input types
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Find the genetics.calculate_similarity function definition
        genetics_func = None
        for func in available_functions:
            if func.get('name') == 'genetics.calculate_similarity':
                genetics_func = func
                break
        
        if not genetics_func:
            return {"error": "genetics.calculate_similarity function not found in available functions"}
        
        # Get parameter schema from function definition
        params_schema = genetics_func.get('parameters', genetics_func.get('params', {}))
        param_names = list(params_schema.keys())
        
        # Create a prompt for LLM to extract species names and determine format
        prompt = f"""Analyze this user query about genetic similarity: "{query_text}"

Extract the following information:
1. First species name (assign to parameter: {param_names[0] if len(param_names) > 0 else 'species1'})
2. Second species name (assign to parameter: {param_names[1] if len(param_names) > 1 else 'species2'})
3. Output format preference (assign to parameter: {param_names[2] if len(param_names) > 2 else 'format'}) - use "percentage" as default

Available parameters for genetics.calculate_similarity:
{json.dumps(params_schema, indent=2)}

Return ONLY valid JSON in this exact format:
{{"species1": "extracted_species_1", "species2": "extracted_species_2", "format": "percentage"}}

Examples:
- "Compare human and chimp genetics" → {{"species1": "human", "species2": "chimp", "format": "percentage"}}
- "What's the DNA similarity between dogs and wolves?" → {{"species1": "dog", "species2": "wolf", "format": "percentage"}}"""

        # Use LLM to extract structured data
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
            validated = FunctionCall(**data)
            
            # Return in the required format
            return {
                "genetics.calculate_similarity": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract species using regex patterns
            species_pattern = r'\b(?:human|chimp|chimpanzee|dog|wolf|cat|mouse|rat|cow|pig|horse|sheep|goat|chicken|fish|bird|plant|tree|bacteria|virus)\b'
            species_matches = re.findall(species_pattern, query_text.lower())
            
            if len(species_matches) >= 2:
                return {
                    "genetics.calculate_similarity": {
                        "species1": species_matches[0].capitalize(),
                        "species2": species_matches[1].capitalize(), 
                        "format": "percentage"
                    }
                }
            else:
                return {"error": f"Failed to parse LLM response and couldn't extract species from query: {e}"}
                
    except Exception as e:
        return {"error": f"Error processing genetics query: {str(e)}"}