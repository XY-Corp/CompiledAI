from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


async def parse_function_call_request(
    user_request: str,
    target_function: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user request to extract numbers list and format as function call structure.
    
    Args:
        user_request: The raw user request containing numbers to calculate average of
        target_function: The name of the function to call (calculate_average)
        
    Returns:
        Function call structure with the target function name as key and parameters as value
    """
    try:
        # Define the expected structure for parsing
        class FunctionCallStructure(BaseModel):
            numbers: List[float]
        
        # Use LLM to extract numbers from the user request
        prompt = f"""Extract all numbers from this user request: "{user_request}"

The user wants to calculate an average, so find all the numbers they mentioned.

Return ONLY a valid JSON array of numbers, like: [12, 15, 18, 20, 21, 26, 30]

Examples:
- "calculate average of 5, 10, 15" → [5, 10, 15]  
- "find the mean of 12.5, 20, 33.2" → [12.5, 20, 33.2]
- "average these: 100, 200, 300, 400" → [100, 200, 300, 400]

Numbers only:"""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON array from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\[.*?\]', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse the numbers array
        numbers_data = json.loads(content)
        
        # Validate it's a list of numbers
        if not isinstance(numbers_data, list):
            # Fallback: try to extract numbers with regex
            number_pattern = r'-?\d+\.?\d*'
            matches = re.findall(number_pattern, user_request)
            numbers_data = [float(match) for match in matches if match]
        
        # Convert to floats and validate
        numbers = []
        for num in numbers_data:
            if isinstance(num, (int, float)):
                numbers.append(float(num))
            elif isinstance(num, str):
                try:
                    numbers.append(float(num))
                except ValueError:
                    continue
        
        if not numbers:
            # Last resort: regex extraction from original request
            number_pattern = r'-?\d+\.?\d*'
            matches = re.findall(number_pattern, user_request)
            numbers = [float(match) for match in matches if match]
        
        # Validate the structure
        validated = FunctionCallStructure(numbers=numbers)
        
        # Return in the required format: function name as top-level key
        return {
            target_function: {
                "numbers": validated.numbers
            }
        }
        
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback to regex extraction
        number_pattern = r'-?\d+\.?\d*'
        matches = re.findall(number_pattern, user_request)
        numbers = [float(match) for match in matches if match]
        
        return {
            target_function: {
                "numbers": numbers
            }
        }
    except Exception as e:
        return {
            target_function: {
                "numbers": []
            }
        }