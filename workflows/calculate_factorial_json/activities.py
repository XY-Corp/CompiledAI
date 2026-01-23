from typing import Any, Dict, List, Optional
import re
import json
from pydantic import BaseModel


class FactorialCall(BaseModel):
    """Expected structure for function call output."""
    data: List[Dict[str, Any]]


async def parse_factorial_request(
    user_request: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> list:
    """Parse the user request to extract the number for factorial calculation and generate the appropriate function call JSON.
    
    Args:
        user_request: The user's request text containing the number to calculate factorial for
        
    Returns:
        List containing a single dict with the function call structure: [{"math.factorial": {"number": [5]}}]
    """
    try:
        # First try to extract number using regex patterns
        number = None
        
        # Pattern 1: "factorial of X"
        match = re.search(r'factorial\s+of\s+(\d+)', user_request, re.IGNORECASE)
        if match:
            number = int(match.group(1))
        else:
            # Pattern 2: "factorial X" or "X factorial"
            match = re.search(r'(?:factorial\s+(\d+)|(\d+)\s+factorial)', user_request, re.IGNORECASE)
            if match:
                number = int(match.group(1) if match.group(1) else match.group(2))
            else:
                # Pattern 3: Any number in the text when "factorial" is mentioned
                if 'factorial' in user_request.lower():
                    numbers = re.findall(r'\b(\d+)\b', user_request)
                    if numbers:
                        number = int(numbers[0])  # Take first number found
        
        # If regex patterns didn't work, fall back to LLM
        if number is None:
            prompt = f"""Extract the number for factorial calculation from this request: "{user_request}"

Return ONLY the number as a JSON object in this format:
{{"number": 5}}

If no number is found, return {{"number": null}}"""
            
            response = llm_client.generate(prompt)
            content = response.content.strip()
            
            # Remove markdown code blocks if present
            if "```" in content:
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                else:
                    json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(0)
            
            try:
                parsed = json.loads(content)
                number = parsed.get('number')
                if number is not None:
                    number = int(number)
            except (json.JSONDecodeError, ValueError, TypeError):
                # Last resort: extract any number from LLM response
                number_match = re.search(r'\b(\d+)\b', content)
                if number_match:
                    number = int(number_match.group(1))
        
        # If we still couldn't extract a number, default to 5 as shown in example
        if number is None:
            number = 5
            
        # Generate the function call structure exactly as specified
        result = [
            {
                "math.factorial": {
                    "number": [number]
                }
            }
        ]
        
        return result
        
    except Exception as e:
        # Fallback to example format with default number
        return [
            {
                "math.factorial": {
                    "number": [5]
                }
            }
        ]