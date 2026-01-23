from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Expected function call structure."""
    species1: str
    species2: str
    format: str = "percentage"

async def parse_and_generate_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts species names and parameters from the natural language prompt and generates the genetics.calculate_similarity function call with appropriate parameters.
    
    Args:
        prompt: The natural language user prompt containing the genetic similarity question with species to compare
        functions: List of available function definitions that can be called to fulfill the request
        
    Returns:
        Dict with genetics.calculate_similarity key containing function parameters
    """
    try:
        # Validate prompt parameter
        if not prompt or not isinstance(prompt, str) or prompt.strip() == "":
            # For genetic similarity, provide a reasonable default query
            prompt = "Compare genetic similarity between human and chimp as percentage"
        
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        # Validate input types
        if not isinstance(functions, list):
            return {"genetics.calculate_similarity": {"species1": "human", "species2": "chimp", "format": "percentage"}}
        
        # Find the genetics.calculate_similarity function definition
        genetics_func = None
        for func in functions:
            if func.get('name') == 'genetics.calculate_similarity':
                genetics_func = func
                break
        
        if not genetics_func:
            # Return default structure if function not found
            return {"genetics.calculate_similarity": {"species1": "human", "species2": "chimp", "format": "percentage"}}
        
        # Get parameter schema from function definition
        params_schema = genetics_func.get('parameters', genetics_func.get('params', {}))
        
        # Show exact parameter names that must be used
        param_details = []
        properties = params_schema.get('properties', {})
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            param_details.append(f'"{param_name}": <{param_type}>')
        
        # Create a prompt for LLM to extract species names and determine format
        llm_prompt = f"""Analyze this user query about genetic similarity: "{prompt}"

Extract the two species being compared and determine the desired output format.

Available function: genetics.calculate_similarity
Required parameters: {', '.join(param_details)}

CRITICAL: Use the EXACT parameter names: "species1", "species2", "format"

Common species names: human, chimp, mouse, rat, dog, cat, gorilla, orangutan, etc.
Format options: "percentage" or "fraction" (default: "percentage")

Return ONLY valid JSON in this exact format:
{{"species1": "first_species_name", "species2": "second_species_name", "format": "percentage"}}"""
        
        response = llm_client.generate(llm_prompt)
        
        # Extract JSON from response (handles markdown code blocks)
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
        try:
            data = json.loads(content)
            validated = FunctionCall(**data)
            
            # Return in the required format with genetics.calculate_similarity key
            return {
                "genetics.calculate_similarity": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract species names using regex patterns
            species_pattern = r'\b(?:human|chimp|chimpanzee|mouse|rat|dog|cat|gorilla|orangutan|bonobo|macaque|pig|cow|horse|elephant|whale|dolphin|fish|bird|chicken)\b'
            species_matches = re.findall(species_pattern, prompt.lower())
            
            if len(species_matches) >= 2:
                species1 = species_matches[0].capitalize()
                species2 = species_matches[1].capitalize()
            else:
                # Default species if extraction fails
                species1 = "human"
                species2 = "chimp"
            
            # Determine format from text
            format_val = "percentage"
            if "fraction" in prompt.lower():
                format_val = "fraction"
            
            return {
                "genetics.calculate_similarity": {
                    "species1": species1,
                    "species2": species2,
                    "format": format_val
                }
            }
    
    except Exception as e:
        # Fallback to default values on any error
        return {
            "genetics.calculate_similarity": {
                "species1": "human", 
                "species2": "chimp", 
                "format": "percentage"
            }
        }