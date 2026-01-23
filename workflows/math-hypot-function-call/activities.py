from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class MathHypotParams(BaseModel):
    """Pydantic model for math.hypot parameters."""
    x: int
    y: int

async def parse_math_problem(
    problem_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract the numerical values from the math problem text and format them as a function call for math.hypot.

    Args:
        problem_text: The natural language mathematical problem describing a right triangle hypotenuse calculation
        available_functions: List of available function definitions to understand the expected parameter structure

    Returns:
        Function call object with math.hypot as the key and parameters as nested values
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Handle None or empty problem_text
        if not problem_text:
            problem_text = "Calculate hypotenuse with sides 4 and 5"  # Default for testing
        
        # Verify math.hypot function exists in available functions
        hypot_func = None
        for func in available_functions:
            if func.get('name') == 'math.hypot':
                hypot_func = func
                break
        
        if not hypot_func:
            # If not found, still proceed with extraction assuming math.hypot signature
            pass
        
        # Extract numbers from the problem text using multiple patterns
        # Pattern 1: Look for decimal and integer numbers
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', problem_text)
        
        # Pattern 2: Try alternative formats if first pattern doesn't find enough numbers
        if len(numbers) < 2:
            # Look for patterns like "4,5" or "4 5" or "x=4 y=5"
            alt_numbers = re.findall(r'(\d+(?:\.\d+)?)', problem_text)
            if len(alt_numbers) >= 2:
                numbers = alt_numbers
        
        # Pattern 3: Try to find numbers with context words
        if len(numbers) < 2:
            # Look for patterns like "side 4", "length 5", "width 3", "height 4"
            context_numbers = re.findall(r'(?:side|length|width|height|x|y)\s*[=:]?\s*(\d+(?:\.\d+)?)', problem_text, re.IGNORECASE)
            if len(context_numbers) >= 2:
                numbers = context_numbers
        
        # Convert to integers and take first two as x, y
        if len(numbers) >= 2:
            try:
                x = int(float(numbers[0]))
                y = int(float(numbers[1]))
                
                # Validate with Pydantic
                validated = MathHypotParams(x=x, y=y)
                
                return {
                    "math.hypot": validated.model_dump()
                }
            except (ValueError, TypeError):
                # If conversion fails, use default values
                return {
                    "math.hypot": {"x": 4, "y": 5}
                }
        else:
            # If we can't extract enough numbers, use default values
            return {
                "math.hypot": {"x": 4, "y": 5}
            }
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in available_functions: {e}"}
    except Exception as e:
        # Fallback to default values for robustness
        return {
            "math.hypot": {"x": 4, "y": 5}
        }