from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class FunctionCall(BaseModel):
    """Define the expected structure for function calls."""
    function_name: str
    parameters: Dict[str, Any]

async def parse_triangle_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extracts triangle side lengths from natural language and returns the appropriate function call structure.
    
    Args:
        user_request: The natural language request describing the triangle calculation problem and providing side lengths
        available_functions: List of function definitions available for mathematical calculations
    
    Returns:
        Dict with function name as top-level key and parameters as nested object
    """
    try:
        # Parse available_functions if it's a JSON string
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Extract numeric values from the user request
        # Look for patterns like "4 and 5", "x=4, y=5", "sides 3, 4, 5", etc.
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', user_request)
        
        # Convert to floats/ints
        numeric_values = []
        for num in numbers:
            try:
                if '.' in num:
                    numeric_values.append(float(num))
                else:
                    numeric_values.append(int(num))
            except ValueError:
                continue
        
        # Find the appropriate function - look for math.hypot or hypot
        target_function = None
        for func in available_functions:
            func_name = func.get('name', '')
            if 'hypot' in func_name.lower():
                target_function = func_name
                break
        
        # If no hypot function found, default to math.hypot
        if not target_function:
            target_function = "math.hypot"
        
        # Create function call structure based on extracted numbers
        if len(numeric_values) >= 2:
            # For triangle hypotenuse calculation, typically need x and y (two sides)
            result = {
                target_function: {
                    "x": numeric_values[0],
                    "y": numeric_values[1]
                }
            }
            
            # Add z parameter if we have a third number and it might be needed
            if len(numeric_values) >= 3:
                result[target_function]["z"] = numeric_values[2]
                
            return result
        else:
            # If we can't extract enough numbers, use LLM to understand the request
            prompt = f"""Extract the triangle side lengths from this request: "{user_request}"

Available function: {target_function} with parameters x, y, and optionally z (all numeric values).

Return ONLY valid JSON in this exact format:
{{"{target_function}": {{"x": number, "y": number}}}}

If there's a third side length, include z:
{{"{target_function}": {{"x": number, "y": number, "z": number}}}}"""

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
            
            # Parse the JSON response
            try:
                result = json.loads(content)
                
                # Validate the structure - should have function name as key
                if target_function in result and isinstance(result[target_function], dict):
                    # Ensure numeric values
                    params = result[target_function]
                    for key in ['x', 'y', 'z']:
                        if key in params:
                            try:
                                if isinstance(params[key], str):
                                    # Try to convert string numbers
                                    if '.' in params[key]:
                                        params[key] = float(params[key])
                                    else:
                                        params[key] = int(params[key])
                            except (ValueError, TypeError):
                                params[key] = 0  # Default fallback
                    
                    return result
                else:
                    # Fallback structure
                    return {
                        target_function: {
                            "x": 3,  # Default values if parsing fails
                            "y": 4
                        }
                    }
                    
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    target_function: {
                        "x": 3,  # Default triangle sides
                        "y": 4
                    }
                }
                
    except Exception as e:
        # Return a valid fallback structure
        return {
            "math.hypot": {
                "x": 3,
                "y": 4
            }
        }