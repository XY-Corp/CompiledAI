from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class MovieRequestParameters(BaseModel):
    """Expected parameters for get_theater_movie_releases function."""
    location: str
    timeframe: int
    format: str

async def parse_movie_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses user request for IMAX movie releases and extracts location, timeframe, and format parameters for the get_theater_movie_releases function.
    
    Args:
        user_request: The raw user request text containing location preferences, time requirements, and movie format specifications
        available_functions: List of available function schemas with their parameter requirements and descriptions
        
    Returns:
        Function call object with get_theater_movie_releases as the top-level key and extracted parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Find the get_theater_movie_releases function
        target_function = None
        for func in available_functions:
            if func.get('name') == 'get_theater_movie_releases':
                target_function = func
                break
        
        if not target_function:
            return {"get_theater_movie_releases": {"location": "unknown", "timeframe": 7, "format": "IMAX"}}
        
        # Get parameter schema
        params_schema = target_function.get('parameters', target_function.get('params', {}))
        
        # Format function details for LLM prompt
        param_details = []
        for param_name, param_info in params_schema.items():
            if isinstance(param_info, str):
                param_type = param_info
            else:
                param_type = param_info.get('type', 'string')
            param_details.append(f'"{param_name}": <{param_type}>')
        
        # Create extraction prompt
        prompt = f"""User request: "{user_request}"

Extract parameters for the get_theater_movie_releases function.

Function parameters required: {{{', '.join(param_details)}}}

Guidelines for extraction:
- location: Extract city, state, or region (e.g., "LA", "New York", "San Francisco")
- timeframe: Extract number of days to look ahead (default 7 if not specified)
- format: Extract movie format preference (IMAX, 3D, standard, etc. - default "IMAX" if not specified)

Return ONLY valid JSON in this exact format:
{{"location": "extracted_location", "timeframe": number, "format": "extracted_format"}}"""

        response = llm_client.generate(prompt)
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
            validated = MovieRequestParameters(**data)
            return {"get_theater_movie_releases": validated.model_dump()}
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback parsing - try to extract with regex
            location = "unknown"
            timeframe = 7
            format_type = "IMAX"
            
            # Extract location patterns
            location_match = re.search(r'\b(?:in|near|at)\s+([A-Za-z\s]+?)(?:\s+for|\s+this|\s+next|$)', user_request, re.IGNORECASE)
            if location_match:
                location = location_match.group(1).strip()
            elif re.search(r'\b(LA|Los Angeles)\b', user_request, re.IGNORECASE):
                location = "LA"
            elif re.search(r'\bNew York\b', user_request, re.IGNORECASE):
                location = "New York"
            
            # Extract timeframe
            time_match = re.search(r'\b(\d+)\s*days?\b', user_request, re.IGNORECASE)
            if time_match:
                timeframe = int(time_match.group(1))
            elif re.search(r'\bthis week\b', user_request, re.IGNORECASE):
                timeframe = 7
            elif re.search(r'\bnext week\b', user_request, re.IGNORECASE):
                timeframe = 14
            
            # Extract format
            if re.search(r'\bIMAX\b', user_request, re.IGNORECASE):
                format_type = "IMAX"
            elif re.search(r'\b3D\b', user_request, re.IGNORECASE):
                format_type = "3D"
            elif re.search(r'\bstandard\b', user_request, re.IGNORECASE):
                format_type = "standard"
            
            return {
                "get_theater_movie_releases": {
                    "location": location,
                    "timeframe": timeframe,
                    "format": format_type
                }
            }
            
    except Exception as e:
        # Final fallback - return default values
        return {
            "get_theater_movie_releases": {
                "location": "unknown",
                "timeframe": 7,
                "format": "IMAX"
            }
        }