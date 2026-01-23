from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Expected structure for the function call extraction."""
    start_city: str
    end_city: str
    transportation: str = "bus"
    allow_transfer: bool = False


async def extract_distance_function_call(
    query_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts function call parameters from natural language distance query using LLM to understand semantic intent and map to city_distance.find_shortest function structure.
    
    Args:
        query_text: The natural language query about finding distance between cities, containing city names and transportation preferences
        available_functions: List of available function definitions providing context for parameter extraction and validation
    
    Returns:
        Dict with city_distance.find_shortest as key containing start_city, end_city, transportation, and allow_transfer parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate inputs
        if not query_text or not query_text.strip():
            # For empty query, still need to return the expected structure
            # Use default values that match the schema
            return {
                "city_distance.find_shortest": {
                    "start_city": "Unknown",
                    "end_city": "Unknown", 
                    "transportation": "bus",
                    "allow_transfer": False
                }
            }
        
        # Find the city_distance.find_shortest function
        target_function = None
        for func in available_functions:
            if func.get('name') == 'city_distance.find_shortest':
                target_function = func
                break
        
        if not target_function:
            return {
                "city_distance.find_shortest": {
                    "start_city": "Unknown",
                    "end_city": "Unknown",
                    "transportation": "bus", 
                    "allow_transfer": False
                }
            }
        
        # Get the function parameters schema
        params_schema = target_function.get('parameters', {})
        properties = params_schema.get('properties', {})
        
        # Create a detailed prompt for the LLM
        param_descriptions = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            param_desc = param_info.get('description', '')
            param_descriptions.append(f'"{param_name}" ({param_type}): {param_desc}')
        
        prompt = f"""Extract the parameters for the city_distance.find_shortest function from this natural language query:

Query: "{query_text}"

Function parameters to extract:
{chr(10).join(param_descriptions)}

CRITICAL: Return ONLY valid JSON in this EXACT format:
{{"start_city": "city_name", "end_city": "city_name", "transportation": "mode", "allow_transfer": true_or_false}}

Rules:
- Use actual city names from the query (e.g. "New York", "Los Angeles")
- For transportation, use values like: "bus", "train", "plane", "car"
- allow_transfer should be true if query mentions connections/transfers, false otherwise
- If transportation not specified, use "bus"
- If allow_transfer not specified, use false

Return only the JSON object, no other text."""

        # Use LLM to extract the parameters
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
            validated = FunctionCall(**data)
            
            # Return in the required format with city_distance.find_shortest as the key
            return {
                "city_distance.find_shortest": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: Try to extract cities using regex patterns
            cities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query_text)
            
            start_city = cities[0] if len(cities) > 0 else "Unknown"
            end_city = cities[1] if len(cities) > 1 else cities[0] if len(cities) == 1 else "Unknown"
            
            # Check for transportation keywords
            transportation = "bus"  # default
            if re.search(r'\b(train|railway)\b', query_text.lower()):
                transportation = "train"
            elif re.search(r'\b(plane|flight|fly)\b', query_text.lower()):
                transportation = "plane"
            elif re.search(r'\b(car|drive)\b', query_text.lower()):
                transportation = "car"
            
            # Check for transfer keywords
            allow_transfer = bool(re.search(r'\b(transfer|connection|connect|change)\b', query_text.lower()))
            
            return {
                "city_distance.find_shortest": {
                    "start_city": start_city,
                    "end_city": end_city,
                    "transportation": transportation,
                    "allow_transfer": allow_transfer
                }
            }
            
    except Exception as e:
        # Return the required structure even on error
        return {
            "city_distance.find_shortest": {
                "start_city": "Unknown",
                "end_city": "Unknown",
                "transportation": "bus",
                "allow_transfer": False
            }
        }