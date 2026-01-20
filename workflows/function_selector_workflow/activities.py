from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCallResult(BaseModel):
    """Defines the expected structure for function call result."""
    function: str
    parameters: Dict[str, Any]


async def analyze_user_intent(
    user_request: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes user request against available functions to determine the appropriate function call with parameters.
    
    Args:
        user_request: The user's natural language request describing what they want to accomplish
        functions: List of available function definitions with name and parameter specifications
        
    Returns:
        Dict with function name and parameters extracted from the user request
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        # Validate that functions is a list
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
        # Format functions with EXACT parameter names clearly visible
        functions_text = "Available Functions:\n"
        for func in functions:
            # Handle both 'parameters' and 'params' keys for compatibility
            params_schema = func.get('parameters', func.get('params', {}))
            
            # Show EXACT parameter names the LLM must use
            param_details = []
            for param_name, param_info in params_schema.items():
                # Handle both string format ("string") and dict format ({"type": "string", ...})
                if isinstance(param_info, str):
                    param_type = param_info
                    param_details.append(f'"{param_name}": <{param_type}>')
                elif isinstance(param_info, dict):
                    param_type = param_info.get('type', 'string')
                    description = param_info.get('description', '')
                    if description:
                        param_details.append(f'"{param_name}": <{param_type}> ({description})')
                    else:
                        param_details.append(f'"{param_name}": <{param_type}>')
                else:
                    param_details.append(f'"{param_name}": <any>')
            
            functions_text += f"- {func['name']}: parameters must be: {{{', '.join(param_details)}}}\n"
        
        # Create prompt for function selection
        prompt = f"""User request: "{user_request}"

{functions_text}

Select the appropriate function and extract parameters from the user request.

CRITICAL RULES:
1. Use the EXACT parameter names shown above for each function
2. DO NOT infer different parameter names
3. Extract parameter values from the user's request
4. If a parameter value is not clear from the request, make a reasonable guess

Return ONLY valid JSON in this exact format:
{{"function": "function_name", "parameters": {{"exact_param_name": "extracted_value"}}}}

Example for get_weather with params {{"location": "string", "unit": "string"}}:
{{"function": "get_weather", "parameters": {{"location": "Paris", "unit": "celsius"}}}}"""
        
        # Use LLM to analyze and select function
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            # Extract content between ```json and ``` or between ``` and ```
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate with Pydantic
        try:
            data = json.loads(content)
            validated = FunctionCallResult(**data)
            return validated.model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract function and parameters using regex
            function_match = re.search(r'"function"\s*:\s*"([^"]+)"', content)
            params_match = re.search(r'"parameters"\s*:\s*(\{[^}]+\})', content)
            
            if function_match:
                function_name = function_match.group(1)
                parameters = {}
                
                if params_match:
                    try:
                        parameters = json.loads(params_match.group(1))
                    except:
                        parameters = {}
                
                return {
                    "function": function_name,
                    "parameters": parameters
                }
            
            return {"error": f"Failed to parse LLM response: {e}"}
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions list: {e}"}
    except KeyError as e:
        return {"error": f"Missing field in function definition: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}