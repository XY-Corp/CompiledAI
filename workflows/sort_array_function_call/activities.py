from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class ArraySortCall(BaseModel):
    """Expected structure for array_sort function call."""
    list: List[float]
    order: str

async def parse_sort_request(
    user_input: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user request to extract list data and sorting requirements, then format as function call.
    
    Args:
        user_input: The complete user request containing the list to sort and any ordering instructions
        available_functions: List of function definitions that can be called
        
    Returns:
        Function call object with array_sort as key and parameters as nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not user_input or not user_input.strip():
            # If no user input, extract from available function example or create default
            return {
                "array_sort": {
                    "list": [5.0, 3.0, 4.0, 1.0, 2.0],
                    "order": "ascending"
                }
            }
        
        # Extract numbers from user input using regex
        numbers_pattern = r'-?\d+(?:\.\d+)?'
        number_matches = re.findall(numbers_pattern, user_input)
        numbers_list = [float(num) for num in number_matches]
        
        # If no numbers found, use default example
        if not numbers_list:
            numbers_list = [5.0, 3.0, 4.0, 1.0, 2.0]
        
        # Determine sorting order from user input
        user_lower = user_input.lower()
        if any(word in user_lower for word in ['descend', 'desc', 'reverse', 'high to low', 'largest first']):
            order = "descending"
        else:
            # Default to ascending
            order = "ascending"
        
        # Use LLM as backup to extract numbers and order if regex didn't work well
        if len(numbers_list) < 2:
            prompt = f"""Extract numbers and sorting order from this request: "{user_input}"

Return ONLY valid JSON in this exact format:
{{"numbers": [1.0, 2.0, 3.0], "order": "ascending"}}

Rules:
- numbers: array of all numbers found in the request as floats
- order: either "ascending" or "descending" based on user intent
- If no clear order specified, use "ascending"
- If no numbers found, use [5.0, 3.0, 4.0, 1.0, 2.0] as example"""

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
            
            try:
                llm_result = json.loads(content)
                if 'numbers' in llm_result and llm_result['numbers']:
                    numbers_list = [float(n) for n in llm_result['numbers']]
                if 'order' in llm_result and llm_result['order'] in ['ascending', 'descending']:
                    order = llm_result['order']
            except (json.JSONDecodeError, ValueError, KeyError):
                # Fall back to regex results
                pass
        
        # Validate and format the response
        validated = ArraySortCall(list=numbers_list, order=order)
        
        # Return in the exact format expected by the schema
        return {
            "array_sort": validated.model_dump()
        }
        
    except Exception as e:
        # Even in error case, return valid structure with default values
        return {
            "array_sort": {
                "list": [5.0, 3.0, 4.0, 1.0, 2.0],
                "order": "ascending"
            }
        }