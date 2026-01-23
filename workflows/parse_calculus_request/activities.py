from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel

class CalcurusDerivativeParams(BaseModel):
    """Pydantic model for calculus.derivative parameters."""
    function: str
    value: float | int
    function_variable: str = "x"

class ParseResult(BaseModel):
    """Structure for the parsed derivative request."""
    calculus_dot_derivative: Dict[str, Any]

async def parse_calculus_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user request to extract function, value, and variable for derivative calculation.
    
    Analyzes user input to extract the mathematical function expression, evaluation point,
    and variable for calculus derivative computation.
    
    Args:
        user_request: The raw user input containing the derivative calculation request
        available_functions: List of available function definitions for context
        
    Returns:
        Dict with 'calculus.derivative' key containing function, value, and function_variable
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Find the calculus.derivative function definition
        calculus_func = None
        for func in available_functions:
            if func.get('name') == 'calculus.derivative':
                calculus_func = func
                break
        
        if not calculus_func:
            return {"calculus.derivative": {"function": "", "value": 0, "function_variable": "x"}}
        
        # Create a clean prompt for the LLM with exact parameter names
        params_schema = calculus_func.get('parameters', {})
        
        prompt = f"""Extract the mathematical function, evaluation point, and variable from this calculus derivative request:

"{user_request}"

The calculus.derivative function requires these EXACT parameters:
- "function": the mathematical expression (e.g., "2x^2", "sin(x)", "x^3 + 2x")
- "value": the numerical point where to evaluate the derivative (integer or float)
- "function_variable": the variable symbol (usually "x", "t", "y", etc.)

Examples:
- "Find derivative of 2x^2 at x=1" → {{"function": "2x^2", "value": 1, "function_variable": "x"}}
- "Derivative of sin(t) when t=0" → {{"function": "sin(t)", "value": 0, "function_variable": "t"}}
- "What's d/dx of x^3 at 2" → {{"function": "x^3", "value": 2, "function_variable": "x"}}

Return ONLY valid JSON with these exact parameter names:
{{"function": "expression", "value": number, "function_variable": "variable"}}"""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = CalcurusDerivativeParams(**data)
            
            # Return in the exact format required by output schema
            return {
                "calculus.derivative": validated.model_dump()
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract using regex patterns
            function_match = re.search(r'(?:function[:\s]+|of[:\s]+|derivative[:\s]+of[:\s]+)([^,\s]+(?:\s*\+\s*[^,\s]+)*)', user_request, re.IGNORECASE)
            value_match = re.search(r'(?:at[:\s]+|when[:\s]+|x\s*=\s*|t\s*=\s*|value[:\s]+)(\d+(?:\.\d+)?)', user_request, re.IGNORECASE)
            var_match = re.search(r'(?:d/d|with respect to[:\s]+)([a-zA-Z])', user_request, re.IGNORECASE)
            
            function_expr = function_match.group(1).strip() if function_match else ""
            value = float(value_match.group(1)) if value_match else 0
            variable = var_match.group(1) if var_match else "x"
            
            # Clean up common function notation
            function_expr = function_expr.replace("**", "^").replace("*", "").strip()
            
            return {
                "calculus.derivative": {
                    "function": function_expr,
                    "value": value,
                    "function_variable": variable
                }
            }
            
    except Exception as e:
        # Return default structure on any error
        return {
            "calculus.derivative": {
                "function": "",
                "value": 0,
                "function_variable": "x"
            }
        }