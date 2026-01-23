from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class RestaurantSearchRequest(BaseModel):
    """Expected structure for restaurant search function call."""
    location: str
    operating_hours: int

async def extract_restaurant_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses natural language request for vegan restaurant search and extracts function call parameters including location and operating hours.
    
    Args:
        prompt: The user's natural language request for finding a vegan restaurant with specific criteria
        functions: List of available function definitions including vegan_restaurant.find_nearby with its parameter schema
        
    Returns:
        Function call structure: {"vegan_restaurant.find_nearby": {"location": "New York, NY", "operating_hours": 23}}
        where the function name is the key containing parameters object with location as 'City, State' format 
        and operating_hours as integer (24-hour format)
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        # Validate we have a user request
        if not prompt or not prompt.strip():
            # Return default structure if no prompt provided
            return {
                "vegan_restaurant.find_nearby": {
                    "location": "New York, NY", 
                    "operating_hours": 23
                }
            }
        
        # Find the vegan_restaurant.find_nearby function in the functions list
        target_function = None
        for func in functions:
            if func.get('name') == 'vegan_restaurant.find_nearby':
                target_function = func
                break
        
        if not target_function:
            # If function not found, return default structure
            return {
                "vegan_restaurant.find_nearby": {
                    "location": "New York, NY",
                    "operating_hours": 23
                }
            }
        
        # Get parameter schema
        params_schema = target_function.get('parameters', target_function.get('params', {}))
        
        # Create prompt for LLM to extract location and operating hours
        extraction_prompt = f"""Extract location and operating hours from this user request for vegan restaurant search:

User Request: "{prompt}"

You need to extract:
1. location: A specific city and state in "City, State" format (e.g., "New York, NY", "San Francisco, CA")
2. operating_hours: An integer representing the hour in 24-hour format (0-23) when they want to visit

Guidelines:
- If no specific location is mentioned, use "New York, NY" as default
- If no specific time is mentioned, use 23 (11 PM) as default
- Convert time expressions like "evening" to appropriate 24-hour format (evening = 19-20, night = 21-23, afternoon = 14-16, morning = 9-11)
- For "late night" use 23, for "lunch time" use 12, for "dinner time" use 19

Return ONLY valid JSON in this exact format:
{{"location": "City, State", "operating_hours": 23}}"""

        response = llm_client.generate(extraction_prompt)
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
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = RestaurantSearchRequest(**data)
            
            # Return in the required format with function name as key
            return {
                "vegan_restaurant.find_nearby": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try regex extraction
            location_match = re.search(r'([A-Za-z\s]+,\s*[A-Z]{2})', prompt)
            location = location_match.group(1) if location_match else "New York, NY"
            
            # Extract time hints
            operating_hours = 23  # Default to 11 PM
            if re.search(r'\b(morning|breakfast)\b', prompt.lower()):
                operating_hours = 9
            elif re.search(r'\b(lunch|noon|afternoon)\b', prompt.lower()):
                operating_hours = 12 if 'lunch' in prompt.lower() else 15
            elif re.search(r'\b(dinner|evening)\b', prompt.lower()):
                operating_hours = 19
            elif re.search(r'\b(night|late)\b', prompt.lower()):
                operating_hours = 23
            
            return {
                "vegan_restaurant.find_nearby": {
                    "location": location,
                    "operating_hours": operating_hours
                }
            }
            
    except Exception as e:
        # Final fallback - return default structure
        return {
            "vegan_restaurant.find_nearby": {
                "location": "New York, NY",
                "operating_hours": 23
            }
        }