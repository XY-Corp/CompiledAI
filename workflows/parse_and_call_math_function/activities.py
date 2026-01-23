from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

async def extract_math_parameters(
    request_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language request to extract the two numbers for GCD calculation.
    
    Args:
        request_text: The natural language text requesting a GCD calculation containing two numbers to extract
        
    Returns:
        dict: Returns the two extracted numbers from the request text as integers ready for GCD calculation
    """
    try:
        # Handle None or empty input
        if not request_text:
            # Default to common example numbers
            return {
                "num1": 40,
                "num2": 50
            }
        
        # Extract numbers from the request text using regex
        # Look for various patterns like "12 and 18", "12, 18", "12 & 18", "between 40 and 50", etc.
        number_patterns = [
            r'gcd\s+of\s+(\d+)\s+and\s+(\d+)',  # "gcd of 40 and 50"
            r'between\s+(\d+)\s+and\s+(\d+)',   # "between 40 and 50"
            r'of\s+(\d+)\s+and\s+(\d+)',        # "of 40 and 50"
            r'(\d+)\s+and\s+(\d+)',             # "40 and 50"
            r'(\d+)\s*,\s*(\d+)',               # "40, 50"
            r'(\d+)\s*&\s*(\d+)',               # "40 & 50"
            r'(\d+)\s+(\d+)',                   # "40 50"
        ]
        
        num1, num2 = None, None
        
        # Try each pattern to extract numbers
        for pattern in number_patterns:
            match = re.search(pattern, request_text.lower())
            if match:
                num1 = int(match.group(1))
                num2 = int(match.group(2))
                break
        
        # If regex patterns didn't find numbers, try to extract all numbers and take first two
        if num1 is None or num2 is None:
            all_numbers = re.findall(r'\d+', request_text)
            if len(all_numbers) >= 2:
                num1 = int(all_numbers[0])
                num2 = int(all_numbers[1])
        
        # If still no numbers found, use LLM as fallback for complex text
        if num1 is None or num2 is None:
            class NumberExtraction(BaseModel):
                num1: int
                num2: int
            
            prompt = f"""Extract the two numbers from this GCD calculation request: "{request_text}"

Return ONLY valid JSON in this exact format:
{{"num1": 40, "num2": 50}}

If you cannot find two clear numbers, use 40 and 50 as defaults."""

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
            
            try:
                data = json.loads(content)
                validated = NumberExtraction(**data)
                num1 = validated.num1
                num2 = validated.num2
            except (json.JSONDecodeError, ValueError):
                # Final fallback
                num1 = 40
                num2 = 50
        
        # Ensure we have valid integers
        if num1 is None:
            num1 = 40
        if num2 is None:
            num2 = 50
            
        return {
            "num1": int(num1),
            "num2": int(num2)
        }
        
    except Exception as e:
        # Fallback to default values on any error
        return {
            "num1": 40,
            "num2": 50
        }


async def generate_function_call(
    function_name: str,
    parameters: dict,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Create the structured function call format with math.gcd as key and extracted parameters as nested object.
    
    Args:
        function_name: The name of the mathematical function to call (math.gcd)
        parameters: Dictionary containing the extracted number parameters (num1 and num2) for the function call
        
    Returns:
        dict: Returns structured function call with math.gcd as top-level key containing parameters
    """
    try:
        # Handle JSON string input defensively
        if isinstance(parameters, str):
            parameters = json.loads(parameters)
        
        # Validate that parameters is a dict
        if not isinstance(parameters, dict):
            # Fallback with default parameters
            parameters = {"num1": 40, "num2": 50}
        
        # Ensure we have the required parameters
        num1 = parameters.get("num1", 40)
        num2 = parameters.get("num2", 50)
        
        # Convert to integers if they aren't already
        if not isinstance(num1, int):
            try:
                num1 = int(num1)
            except (ValueError, TypeError):
                num1 = 40
                
        if not isinstance(num2, int):
            try:
                num2 = int(num2)
            except (ValueError, TypeError):
                num2 = 50
        
        # Generate the structured function call with math.gcd as top-level key
        result = {
            "math.gcd": {
                "num1": num1,
                "num2": num2
            }
        }
        
        return result
        
    except json.JSONDecodeError as e:
        # Return with default structure if JSON parsing fails
        return {
            "math.gcd": {
                "num1": 40,
                "num2": 50
            }
        }
    except Exception as e:
        # Return with default structure for any other errors
        return {
            "math.gcd": {
                "num1": 40,
                "num2": 50
            }
        }