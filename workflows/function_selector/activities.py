from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCall(BaseModel):
    """Represents a function call with name and parameters."""
    function: str
    parameters: dict


async def analyze_request_and_select_function(
    user_request: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user request against available functions to select the best match and extract parameters.
    
    Args:
        user_request: The user's natural language request that needs to be mapped to a function call
        functions: List of available function definitions containing name and parameter specifications
        
    Returns:
        Dict with 'function' and 'parameters' keys containing the selected function call
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
            
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
            
        if not functions:
            return {"error": "No functions available"}
            
        # Format functions with EXACT parameter names clearly visible
        functions_text = "Available Functions:\n"
        for func in functions:
            func_name = func.get('name', 'unknown')
            # Check both 'parameters' and 'params' keys for compatibility
            params_schema = func.get('parameters', func.get('params', {}))
            
            # Show EXACT parameter names the LLM must use
            param_details = []
            for param_name, param_info in params_schema.items():
                # Handle both string format ("string") and dict format ({"type": "string", ...})
                if isinstance(param_info, str):
                    param_type = param_info
                else:
                    param_type = param_info.get('type', 'string')
                param_details.append(f'"{param_name}": <{param_type}>')
                
            functions_text += f"- {func_name}: parameters must be: {{{', '.join(param_details)}}}\n"
            
        prompt = f"""User request: "{user_request}"

{functions_text}

Select the appropriate function and extract parameters from the user request.

CRITICAL: Use the EXACT parameter names shown above for each function.
DO NOT infer different parameter names.

Return ONLY valid JSON in this exact format:
{{"function": "function_name", "parameters": {{"exact_param_name": "extracted_value"}}}}

Examples:
- For get_weather with params {{"location": "string", "unit": "string"}}: 
  {{"function": "get_weather", "parameters": {{"location": "Paris", "unit": "celsius"}}}}
- For send_email with params {{"to": "string", "subject": "string", "body": "string"}}:
  {{"function": "send_email", "parameters": {{"to": "john@example.com", "subject": "Hello", "body": "Hi there"}}}}"""

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
            validated = FunctionCall(**data)
            return validated.model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback parsing attempt
            try:
                # Try to extract function name and parameters using regex
                func_match = re.search(r'"function":\s*"([^"]+)"', content)
                params_match = re.search(r'"parameters":\s*(\{[^}]*\})', content)
                
                if func_match:
                    function_name = func_match.group(1)
                    parameters = {}
                    
                    if params_match:
                        try:
                            parameters = json.loads(params_match.group(1))
                        except json.JSONDecodeError:
                            # Extract key-value pairs manually
                            param_pairs = re.findall(r'"([^"]+)":\s*"([^"]+)"', params_match.group(1))
                            parameters = dict(param_pairs)
                    
                    return {
                        "function": function_name,
                        "parameters": parameters
                    }
            except Exception:
                pass
                
            return {"error": f"Failed to parse LLM response: {e}"}
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions input: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}