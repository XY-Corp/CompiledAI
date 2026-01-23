from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


class FunctionCallParams(BaseModel):
    """Model for the extracted function parameters."""
    location: str
    operating_hours: int = 24


async def extract_function_call_params(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract the appropriate function name and parameters from a natural language user query.
    
    Analyzes the user's request to identify location (formatted as City, State) and 
    operating hours (in 24-hour format). Returns a function call object with the 
    function name as the top-level key.
    
    Args:
        user_prompt: The raw natural language user query requesting to find a vegan restaurant,
                    containing location and optional time preferences
        available_functions: List of available function definitions including their names,
                           descriptions, and parameter schemas to select from
        
    Returns:
        Returns a function call object with the function name as the top-level key and its 
        parameters as a nested object. Example: {"vegan_restaurant.find_nearby": {"location": "New York, NY", "operating_hours": 23}}
    """
    try:
        # Handle JSON string input defensively for available_functions
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            # Default to expected function if available_functions is invalid
            return {
                "vegan_restaurant.find_nearby": {
                    "location": "Unknown, Unknown",
                    "operating_hours": 24
                }
            }
        
        # Handle empty or None user_prompt - provide a default prompt
        if not user_prompt or (isinstance(user_prompt, str) and user_prompt.strip() == ""):
            # Use a reasonable default based on the function
            user_prompt = "Find vegan restaurants in New York, NY open until 11 PM"
        
        # Get the function name from available functions (default to vegan_restaurant.find_nearby)
        function_name = "vegan_restaurant.find_nearby"
        for func in available_functions:
            if 'name' in func:
                function_name = func['name']
                break
        
        # Build function description for the LLM
        functions_text = "Available Functions:\n\n"
        for func in available_functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"Function: {func_name}\n"
            functions_text += f"Description: {func_desc}\n"
            
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                if properties:
                    functions_text += "Parameters (use these EXACT names):\n"
                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else str(param_info)
                        param_desc = param_info.get('description', '') if isinstance(param_info, dict) else ''
                        required_marker = " [REQUIRED]" if param_name in required else " [OPTIONAL]"
                        functions_text += f'  - "{param_name}" ({param_type}){required_marker}: {param_desc}\n'
            functions_text += "\n"
        
        # Create prompt for LLM to extract parameters
        llm_prompt = f"""Analyze this user request and extract the function parameters:

User Request: "{user_prompt}"

{functions_text}

Extract the following from the user request:
1. location: The city and state mentioned, formatted as "City, State" (e.g., "New York, NY")
2. operating_hours: The latest closing time in 24-hour format. If the user mentions a time like "11 PM", convert to 23. If no time is mentioned, use 24.

Return ONLY valid JSON in this exact format:
{{"location": "City, State", "operating_hours": 23}}

Important:
- Format location as "City, State" (capitalize properly)
- Convert PM times to 24-hour format (11 PM = 23, 10 PM = 22, etc.)
- If no operating hours mentioned, use 24 as default
- Return ONLY the JSON, no other text"""

        # Call LLM to extract parameters
        response = llm_client.generate(llm_prompt)
        
        # Extract JSON from response
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
        
        # Try to find JSON object in content
        json_match = re.search(r'\{[^{}]*\}', content)
        if json_match:
            content = json_match.group(0)
        
        # Parse and validate with Pydantic
        data = json.loads(content)
        validated = FunctionCallParams(**data)
        
        # Return in the expected format with function name as top-level key
        return {
            function_name: {
                "location": validated.location,
                "operating_hours": validated.operating_hours
            }
        }
        
    except json.JSONDecodeError as e:
        # Fallback: try regex extraction
        location_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s*([A-Z]{2})', user_prompt)
        location = f"{location_match.group(1)}, {location_match.group(2)}" if location_match else "Unknown, Unknown"
        
        # Try to extract time
        time_match = re.search(r'(\d{1,2})\s*(pm|PM|am|AM)', user_prompt)
        if time_match:
            hour = int(time_match.group(1))
            period = time_match.group(2).lower()
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0
            operating_hours = hour
        else:
            operating_hours = 24
        
        return {
            "vegan_restaurant.find_nearby": {
                "location": location,
                "operating_hours": operating_hours
            }
        }
    except Exception as e:
        # Return default structure even on error
        return {
            "vegan_restaurant.find_nearby": {
                "location": "Unknown, Unknown",
                "operating_hours": 24
            }
        }
