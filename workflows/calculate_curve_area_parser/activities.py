from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel, ValidationError

class FunctionCall(BaseModel):
    """Structure for function call with parameters."""
    function: str
    interval: List[float]
    method: Optional[str] = None

class ParsedOutput(BaseModel):
    """Expected output structure for mathematical function parsing."""
    calculate_area_under_curve: FunctionCall

async def parse_mathematical_request(
    request_text: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract mathematical function, interval bounds, and method from natural language request.
    
    Args:
        request_text: Natural language mathematical request containing function definition and integration bounds
        available_functions: List of available function definitions with their parameter schemas
        
    Returns:
        Dict with function call structure: {"calculate_area_under_curve": {"function": "x^2", "interval": [1.0, 3.0], "method": "trapezoidal"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Find the calculate_area_under_curve function schema
        target_function = None
        for func in available_functions:
            if func.get('name') == 'calculate_area_under_curve':
                target_function = func
                break
        
        if not target_function:
            return {"error": "calculate_area_under_curve function not found in available_functions"}
        
        # Get parameter schema
        params_schema = target_function.get('parameters', {})
        
        # Build prompt for LLM with exact parameter requirements
        param_details = []
        for param_name, param_info in params_schema.items():
            if isinstance(param_info, dict):
                param_type = param_info.get('type', 'string')
                description = param_info.get('description', '')
                param_details.append(f'"{param_name}": {param_type} - {description}')
            else:
                param_details.append(f'"{param_name}": {param_info}')
        
        prompt = f"""Extract mathematical function parameters from this request: "{request_text}"

The function "calculate_area_under_curve" requires these exact parameters:
{chr(10).join('- ' + detail for detail in param_details)}

Extract the mathematical function expression and interval bounds from the request.
Convert mathematical notation to Python syntax (e.g., x^2 -> x**2, x² -> x**2).
Convert interval notation like [1,3] or "from 1 to 3" to [1.0, 3.0].

Return ONLY valid JSON in this exact format:
{{"function": "x**2", "interval": [1.0, 3.0], "method": "trapezoidal"}}

If no method is specified, include "method": "trapezoidal" as default."""

        # Use llm_client to extract structured data
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
        
        # Parse and validate the extracted parameters
        try:
            extracted_params = json.loads(content)
            
            # Validate structure
            validated = FunctionCall(**extracted_params)
            
            # Return in the exact required format
            result = {
                "calculate_area_under_curve": validated.model_dump()
            }
            
            return result
            
        except (json.JSONDecodeError, ValidationError) as e:
            # Fallback: try to extract with regex patterns
            function_match = re.search(r'(?:f\(x\)\s*=\s*|function\s+|integrate\s+)([x\^*+\-0-9\s\(\)\.]+)', request_text, re.IGNORECASE)
            interval_match = re.search(r'(?:from\s+|between\s+|\[)(\d+(?:\.\d+)?)\s*(?:to\s+|,\s*|\s+and\s+)(\d+(?:\.\d+)?)(?:\s*\])?', request_text, re.IGNORECASE)
            
            if function_match and interval_match:
                function_expr = function_match.group(1).strip()
                # Convert common mathematical notation to Python
                function_expr = function_expr.replace('^', '**')
                function_expr = re.sub(r'(\d)x', r'\1*x', function_expr)  # 2x -> 2*x
                
                start = float(interval_match.group(1))
                end = float(interval_match.group(2))
                
                result = {
                    "calculate_area_under_curve": {
                        "function": function_expr,
                        "interval": [start, end],
                        "method": "trapezoidal"
                    }
                }
                return result
            else:
                return {"error": f"Failed to parse mathematical request: {e}"}
                
    except Exception as e:
        return {"error": f"Error processing request: {str(e)}"}