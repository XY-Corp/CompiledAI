from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

async def parse_and_format_function_call(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parses the user's natural language request to extract the list of numbers and formats them as a proper function call for calculate_average.
    
    Args:
        user_request: The natural language user request containing the instruction to calculate average and the specific list of numbers to process
        available_functions: List of available function definitions that provide context for the expected output format and parameter structure
        
    Returns:
        Function call object with the function name as the top-level key and its parameters as a nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Define expected structure for LLM response
        class NumbersList(BaseModel):
            numbers: List[float]
        
        # Extract numbers from user request using LLM
        prompt = f"""Extract all numbers from this user request and return them as a JSON array of floats: "{user_request}"

Return ONLY valid JSON in this exact format:
{{"numbers": [1.0, 2.0, 3.0]}}

Do not include any explanations, just the JSON with the extracted numbers."""

        response = llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
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
            validated = NumbersList(**data)
            
            # Return in the exact format specified by the output schema
            return {
                "calculate_average": {
                    "numbers": validated.numbers
                }
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract numbers using regex
            numbers = re.findall(r'-?\d+\.?\d*', user_request)
            if numbers:
                float_numbers = [float(num) for num in numbers]
                return {
                    "calculate_average": {
                        "numbers": float_numbers
                    }
                }
            else:
                # If no numbers found, return empty list to match expected structure
                return {
                    "calculate_average": {
                        "numbers": []
                    }
                }
                
    except Exception as e:
        # Always return the expected structure, even on error
        return {
            "calculate_average": {
                "numbers": []
            }
        }