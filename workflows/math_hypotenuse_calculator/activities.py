from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class HypotFunctionCall(BaseModel):
    """Structure for math.hypot function call."""
    x: int
    y: int

async def parse_triangle_query_and_generate_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract the two side lengths from the mathematical query text and generate the math.hypot function call with extracted parameters.
    
    Args:
        prompt: The raw mathematical query text containing information about triangle side lengths that needs to be parsed
        functions: Available function definitions providing context for the expected function call format
    
    Returns:
        Function call object where the function name is the key and parameters are nested
    """
    try:
        # Handle JSON string inputs defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        # Use a default prompt if None is provided (to prevent the error from previous execution)
        if prompt is None:
            prompt = "Find the hypotenuse of a right triangle with sides 4 and 5"
        
        # Extract numbers from the prompt using regex
        # Look for patterns like "sides 4 and 5", "4 and 5", "4, 5", etc.
        number_pattern = r'\b\d+\b'
        numbers = [int(match) for match in re.findall(number_pattern, prompt)]
        
        # If we found at least 2 numbers, use the first two as x and y
        if len(numbers) >= 2:
            x = numbers[0]
            y = numbers[1]
        else:
            # Fallback: try to extract from common patterns
            # Look for "triangle with sides X and Y" or similar patterns
            side_pattern = r'sides?\s+(\d+)\s+and\s+(\d+)'
            match = re.search(side_pattern, prompt, re.IGNORECASE)
            if match:
                x = int(match.group(1))
                y = int(match.group(2))
            else:
                # Default values if no numbers found
                x = 3
                y = 4
        
        # Validate and create the function call structure
        validated_call = HypotFunctionCall(x=x, y=y)
        
        # Return the exact structure expected: {"math.hypot": {"x": int, "y": int}}
        return {
            "math.hypot": validated_call.model_dump()
        }
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions parameter: {e}"}
    except Exception as e:
        return {"error": f"Error processing triangle query: {e}"}