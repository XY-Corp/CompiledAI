from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


async def extract_bird_parameters(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract bird characteristics from natural language prompt and map to identify_bird function parameters.
    
    Args:
        prompt: The natural language bird identification request containing bird characteristics
        functions: List of available function definitions to understand the expected parameter structure
        
    Returns:
        Dict with identify_bird as key and extracted parameters as nested dict containing color, habitat, and size
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        # Find the identify_bird function definition
        identify_bird_func = None
        for func in functions:
            if func.get('name') == 'identify_bird':
                identify_bird_func = func
                break
        
        if not identify_bird_func:
            return {"error": "identify_bird function not found in available functions"}
        
        # Get parameter schema
        params_schema = identify_bird_func.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Create a structured prompt for the LLM
        prompt_text = f"""Extract bird identification parameters from this request: "{prompt or ''}"

Based on the text, identify:
- color: The bird's color (any color mentioned)
- habitat: The bird's habitat/environment (forest, wetland, urban, etc.)
- size: The bird's size (must be exactly: small, medium, or large - default to small if not clear)

Return ONLY valid JSON in this exact format:
{{"color": "extracted_color", "habitat": "extracted_habitat", "size": "small"}}

If information is missing, make reasonable defaults:
- color: use "unknown" if no color mentioned
- habitat: use "unknown" if no habitat mentioned  
- size: use "small" if no size mentioned"""

        # Use LLM to extract parameters
        response = llm_client.generate(prompt_text)
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
        
        # Parse the JSON response
        try:
            extracted_params = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: extract with regex patterns
            extracted_params = {}
            
            # Extract color
            color_match = re.search(r'\b(red|blue|green|yellow|black|white|brown|gray|orange|purple)\b', (prompt or '').lower())
            extracted_params['color'] = color_match.group(1) if color_match else 'unknown'
            
            # Extract habitat
            habitat_match = re.search(r'\b(forest|woods|wetland|marsh|urban|city|park|field|meadow|lake|river|ocean|beach)\b', (prompt or '').lower())
            extracted_params['habitat'] = habitat_match.group(1) if habitat_match else 'unknown'
            
            # Extract size
            if re.search(r'\b(large|big|huge)\b', (prompt or '').lower()):
                extracted_params['size'] = 'large'
            elif re.search(r'\b(medium|mid-sized)\b', (prompt or '').lower()):
                extracted_params['size'] = 'medium'
            else:
                extracted_params['size'] = 'small'
        
        # Validate and clean parameters
        clean_params = {
            'color': str(extracted_params.get('color', 'unknown')),
            'habitat': str(extracted_params.get('habitat', 'unknown')), 
            'size': str(extracted_params.get('size', 'small'))
        }
        
        # Ensure size is valid enum value
        if clean_params['size'] not in ['small', 'medium', 'large']:
            clean_params['size'] = 'small'
        
        # Return in the required format with identify_bird as the top-level key
        return {
            "identify_bird": clean_params
        }
        
    except Exception as e:
        return {"error": f"Failed to extract bird parameters: {str(e)}"}