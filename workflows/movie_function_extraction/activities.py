from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

async def parse_movie_request(
    user_prompt: str,
    function_definitions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract function parameters from user movie request using LLM to identify location, timeframe, and format specifications.
    
    Args:
        user_prompt: The complete user request text containing movie search criteria including location, timeframe, and format preferences
        function_definitions: List of available function definitions to provide context for parameter extraction
        
    Returns:
        Function call object with get_theater_movie_releases as the key and parameters object containing location, timeframe, and format
    """
    try:
        # Handle JSON string input defensively
        if isinstance(function_definitions, str):
            function_definitions = json.loads(function_definitions)
        
        if not isinstance(function_definitions, list):
            return {"get_theater_movie_releases": {"location": "unknown", "timeframe": 7, "format": "all"}}
        
        # Find the get_theater_movie_releases function
        target_function = None
        for func in function_definitions:
            if func.get('name') == 'get_theater_movie_releases':
                target_function = func
                break
        
        if not target_function:
            return {"get_theater_movie_releases": {"location": "unknown", "timeframe": 7, "format": "all"}}
        
        # Get parameter schema
        params_schema = target_function.get('parameters', target_function.get('params', {}))
        
        # Format function details for LLM prompt  
        param_details = []
        for param_name, param_info in params_schema.items():
            if isinstance(param_info, str):
                param_type = param_info
                param_desc = ""
            else:
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '')
            param_details.append(f'"{param_name}": <{param_type}> - {param_desc}')
        
        # Create extraction prompt
        prompt = f"""User request: "{user_prompt}"

Target function: get_theater_movie_releases
Required parameters: {{{', '.join(param_details)}}}

Extract the following parameters from the user request:
- location: A city/region string (e.g., "LA", "New York", "Chicago")  
- timeframe: Number of days from current date as integer (default: 7)
- format: Movie format string - one of: "IMAX", "2D", "3D", "4DX", or "all" (default: "all")

Guidelines:
- For location: Extract city names, abbreviations, or region references
- For timeframe: Look for phrases like "next week" (7), "this weekend" (2-3), "next month" (30)
- For format: Look for specific format mentions like IMAX, 3D, 4DX, or assume "all"

Return ONLY valid JSON in this exact format:
{{"location": "extracted_city", "timeframe": number, "format": "extracted_format"}}"""

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
        
        # Validate the extracted parameters
        class MovieParams(BaseModel):
            location: str
            timeframe: int = 7
            format: str = "all"
        
        try:
            params_data = json.loads(content)
            validated_params = MovieParams(**params_data)
            
            # Return in the required format
            return {
                "get_theater_movie_releases": validated_params.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback extraction using regex patterns
            location = "unknown"
            timeframe = 7
            format_type = "all"
            
            # Try to extract location with regex
            location_patterns = [
                r'\b(LA|Los Angeles|NYC|New York|Chicago|Miami|Boston|Seattle|Portland|Denver|Austin|Dallas|Houston)\b',
                r'in\s+([A-Za-z\s]+?)(?:\s+area|\s+region|$)',
                r'near\s+([A-Za-z\s]+?)(?:\s|$)'
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, user_prompt, re.IGNORECASE)
                if match:
                    location = match.group(1).strip()
                    break
            
            # Try to extract timeframe
            if re.search(r'\b(?:this\s+)?weekend\b', user_prompt, re.IGNORECASE):
                timeframe = 3
            elif re.search(r'\bnext\s+week\b', user_prompt, re.IGNORECASE):
                timeframe = 7
            elif re.search(r'\bthis\s+week\b', user_prompt, re.IGNORECASE):
                timeframe = 7
            elif re.search(r'\bnext\s+month\b', user_prompt, re.IGNORECASE):
                timeframe = 30
            elif re.search(r'\btoday\b', user_prompt, re.IGNORECASE):
                timeframe = 1
                
            # Try to extract format
            if re.search(r'\bIMAX\b', user_prompt, re.IGNORECASE):
                format_type = "IMAX"
            elif re.search(r'\b3D\b', user_prompt, re.IGNORECASE):
                format_type = "3D"
            elif re.search(r'\b4DX\b', user_prompt, re.IGNORECASE):
                format_type = "4DX"
            elif re.search(r'\b2D\b', user_prompt, re.IGNORECASE):
                format_type = "2D"
            
            return {
                "get_theater_movie_releases": {
                    "location": location,
                    "timeframe": timeframe,
                    "format": format_type
                }
            }
            
    except Exception as e:
        # Final fallback with default values
        return {
            "get_theater_movie_releases": {
                "location": "unknown",
                "timeframe": 7,
                "format": "all"
            }
        }