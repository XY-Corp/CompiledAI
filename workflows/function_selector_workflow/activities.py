from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Function call result."""
    function: str
    parameters: Dict[str, Any]


async def analyze_request_and_select_function(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user request against available functions to determine the appropriate function to call and extract parameters.

    Args:
        user_request: The user's natural language request that needs to be mapped to a function call
        available_functions: List of function definitions with their names and parameter schemas that can be called

    Returns:
        Dict with exact structure: {"function": "function_name", "parameters": {...}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        # Format functions with EXACT parameter names clearly visible
        functions_text = "Available Functions:\n"
        for func in available_functions:
            func_name = func.get('name', 'unknown')
            # Handle both 'parameters' and 'params' keys for compatibility
            params_schema = func.get('parameters', func.get('params', {}))
            
            # Show EXACT parameter names the LLM must use
            if params_schema:
                param_details = []
                for param_name, param_info in params_schema.items():
                    # Handle both string format ("string") and dict format ({"type": "string", ...})
                    if isinstance(param_info, str):
                        param_type = param_info
                        param_details.append(f'"{param_name}": <{param_type}>')
                    elif isinstance(param_info, dict):
                        param_type = param_info.get('type', 'any')
                        param_details.append(f'"{param_name}": <{param_type}>')
                    else:
                        param_details.append(f'"{param_name}": <any>')
                
                functions_text += f"- {func_name}: parameters must be: {{{', '.join(param_details)}}}\n"
            else:
                functions_text += f"- {func_name}: no parameters\n"
        
        prompt = f"""User request: "{user_request}"

{functions_text}

Select the most appropriate function and extract parameters from the user request.

CRITICAL: Use the EXACT parameter names shown above for each function.
DO NOT infer different parameter names.

For example, if get_weather has parameters {{"location": "string", "unit": "celsius|fahrenheit"}}:
- User says "weather in Paris in Celsius"
- Return: {{"function": "get_weather", "parameters": {{"location": "Paris", "unit": "celsius"}}}}

Return ONLY valid JSON in this exact format:
{{"function": "function_name", "parameters": {{"exact_param_name": "extracted_value"}}}}

If no function matches, use the closest match."""

        response = llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
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
        data = json.loads(content)
        validated = FunctionCall(**data)
        
        return {
            "function": validated.function,
            "parameters": validated.parameters
        }
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse LLM response as JSON: {e}"}
    except Exception as e:
        return {"error": f"Error processing request: {e}"}