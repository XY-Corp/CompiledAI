from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

async def extract_bird_parameters(
    user_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract bird characteristics from user text and format as function call parameters.
    
    Args:
        user_text: The user's natural language description of the bird they want to identify
        available_functions: List of function specifications to understand parameter requirements and constraints
        
    Returns:
        Dict with identify_bird as key and extracted parameters as nested dict
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Find the identify_bird function definition
        identify_bird_func = None
        for func in available_functions:
            if func.get('name') == 'identify_bird':
                identify_bird_func = func
                break
        
        if not identify_bird_func:
            return {"error": "identify_bird function not found in available functions"}
        
        # Get parameter schema - handle both 'parameters' and 'params' keys
        params_schema = identify_bird_func.get('parameters', identify_bird_func.get('params', {}))
        properties = params_schema.get('properties', {})
        
        if not properties:
            return {"error": "No parameter properties found for identify_bird function"}
        
        # Define the expected structure for validation
        class BirdParameters(BaseModel):
            color: str = ""
            habitat: str = ""
            size: str = ""
        
        # Create a structured prompt for the LLM with EXACT parameter names
        param_names = list(properties.keys())
        prompt = f"""Extract bird identification parameters from this user request: "{user_text or ''}"

Available parameters to extract (use these EXACT names):
{', '.join(f'"{name}"' for name in param_names)}

Examples of values:
- color: "red", "blue", "green", "brown", "black", "white", "yellow", etc.
- habitat: "forest", "wetland", "urban", "grassland", "mountain", "desert", etc.
- size: "small", "medium", "large", "tiny", "huge", etc.

Return ONLY valid JSON in this exact format:
{{"color": "extracted_color", "habitat": "extracted_habitat", "size": "extracted_size"}}

If a characteristic is not mentioned, use an empty string for that field."""
        
        # Use LLM to extract parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
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
            validated = BirdParameters(**data)
            extracted_params = validated.model_dump()
            
            # Return in the required format: {"identify_bird": {...}}
            return {
                "identify_bird": extracted_params
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            fallback_params = {}
            
            # Extract color
            color_match = re.search(r'\b(red|blue|green|brown|black|white|yellow|orange|purple|gray|grey)\b', user_text.lower())
            fallback_params["color"] = color_match.group(1) if color_match else ""
            
            # Extract habitat
            habitat_match = re.search(r'\b(forest|wetland|urban|grassland|mountain|desert|park|garden|lake|river)\b', user_text.lower())
            fallback_params["habitat"] = habitat_match.group(1) if habitat_match else ""
            
            # Extract size
            size_match = re.search(r'\b(small|medium|large|tiny|huge|big|little)\b', user_text.lower())
            fallback_params["size"] = size_match.group(1) if size_match else ""
            
            return {
                "identify_bird": fallback_params
            }
            
    except Exception as e:
        return {"error": f"Failed to extract bird parameters: {str(e)}"}