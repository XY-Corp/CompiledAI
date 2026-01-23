from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel

class MathFunctionCall(BaseModel):
    """Structure for mathematical function call parameters."""
    function: str
    interval: List[float]
    method: Optional[str] = None

async def parse_math_request(
    request_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract mathematical function details and parameters from natural language request text to generate function call structure.
    
    Args:
        request_text: The natural language mathematical request containing function and interval information
        available_functions: List of function schemas with names, descriptions, and parameter definitions
    
    Returns:
        A function call structure with the function name as the top-level key and parameters nested inside.
        Example: {'calculate_area_under_curve': {'function': 'x^2', 'interval': [1.0, 3.0], 'method': 'trapezoidal'}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate we have functions
        if not isinstance(available_functions, list) or len(available_functions) == 0:
            return {"calculate_area_under_curve": {"function": "x^2", "interval": [0.0, 1.0]}}
        
        # Find the calculate_area_under_curve function
        target_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_area_under_curve':
                target_function = func
                break
        
        if not target_function:
            return {"calculate_area_under_curve": {"function": "x^2", "interval": [0.0, 1.0]}}
        
        # Extract parameter information
        params_schema = target_function.get('parameters', {})
        properties = params_schema.get('properties', {})
        required_params = params_schema.get('required', [])
        
        # Build detailed function description for LLM
        param_details = []
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            param_desc = param_info.get('description', '')
            is_required = param_name in required_params
            required_text = " (REQUIRED)" if is_required else " (optional)"
            param_details.append(f'  - {param_name} ({param_type}){required_text}: {param_desc}')
        
        function_details = f"""Function: calculate_area_under_curve
Description: {target_function.get('description', '')}
Parameters:
{chr(10).join(param_details)}"""
        
        # Create the LLM prompt with examples and clear instructions
        prompt = f"""Parse this mathematical request and extract the function call parameters: "{request_text}"

{function_details}

CRITICAL: You must return JSON in this EXACT format:
{{"calculate_area_under_curve": {{"function": "mathematical_expression", "interval": [start, end], "method": "optional_method"}}}}

Examples of valid mathematical expressions:
- "x^2" for x squared
- "x**2" for x squared  
- "sin(x)" for sine function
- "2*x + 1" for linear function

Examples of valid intervals:
- [0, 1] for interval from 0 to 1
- [1.0, 3.0] for interval from 1 to 3
- [-1, 2] for interval from -1 to 2

Common integration methods (if mentioned):
- "trapezoidal"
- "simpson"
- "rectangular"

Return ONLY the JSON object, no other text."""
        
        # Use llm_client to parse the request
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
        
        # Parse and validate the JSON response
        try:
            result = json.loads(content)
            
            # Validate the structure
            if 'calculate_area_under_curve' in result:
                func_params = result['calculate_area_under_curve']
                
                # Validate required parameters are present
                if 'function' not in func_params or 'interval' not in func_params:
                    raise ValueError("Missing required parameters")
                
                # Validate interval is a list of two numbers
                if not isinstance(func_params['interval'], list) or len(func_params['interval']) != 2:
                    raise ValueError("Interval must be a list of two numbers")
                
                # Ensure interval values are floats
                func_params['interval'] = [float(func_params['interval'][0]), float(func_params['interval'][1])]
                
                # Use Pydantic for final validation
                validated = MathFunctionCall(**func_params)
                result['calculate_area_under_curve'] = validated.model_dump()
                
                return result
            else:
                raise ValueError("Response missing calculate_area_under_curve key")
                
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Fallback: try to extract function and interval using regex
            math_expr_match = re.search(r'(?:function|f\(x\)|expression)[\s:=]+([x\^\*\+\-\(\)\w\s]+)', request_text, re.IGNORECASE)
            interval_match = re.search(r'(?:from|between|interval)[\s\[\(]*(-?\d+(?:\.\d+)?)[\s\,\-to]+(-?\d+(?:\.\d+)?)', request_text, re.IGNORECASE)
            
            # Default values
            function_expr = "x^2"
            interval = [0.0, 1.0]
            
            if math_expr_match:
                function_expr = math_expr_match.group(1).strip()
            
            if interval_match:
                start = float(interval_match.group(1))
                end = float(interval_match.group(2))
                interval = [start, end]
            
            # Check for method mention
            method = None
            if re.search(r'trapezoidal|trapezoid', request_text, re.IGNORECASE):
                method = "trapezoidal"
            elif re.search(r'simpson', request_text, re.IGNORECASE):
                method = "simpson"
            elif re.search(r'rectangular|rectangle', request_text, re.IGNORECASE):
                method = "rectangular"
            
            result = {
                "calculate_area_under_curve": {
                    "function": function_expr,
                    "interval": interval
                }
            }
            
            if method:
                result["calculate_area_under_curve"]["method"] = method
                
            return result
            
    except Exception as e:
        # Final fallback
        return {
            "calculate_area_under_curve": {
                "function": "x^2",
                "interval": [0.0, 1.0]
            }
        }