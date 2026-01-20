from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionCallResult(BaseModel):
    """Expected structure for function call selection."""
    function: str
    parameters: dict


async def parse_user_intent(
    user_request: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user request to understand intent and extract parameters, then selects the appropriate function from the available list.
    
    Args:
        user_request: The natural language user request that needs to be interpreted and mapped to a function call
        functions: List of available functions with their parameter schemas that can be called to fulfill the user request
    
    Returns:
        Dict with 'function' and 'parameters' keys containing the selected function call structure
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"function": "", "parameters": {}, "error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"function": "", "parameters": {}, "error": "No functions available"}
        
        # Format functions with EXACT parameter names clearly visible
        functions_text = "Available Functions:\n"
        for func in functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', '')
            
            # Check both 'parameters' and 'params' keys for compatibility
            params_schema = func.get('parameters', func.get('params', {}))
            
            # Show EXACT parameter names the LLM must use
            param_details = []
            for param_name, param_info in params_schema.items():
                # Handle both string format ("string") and dict format ({"type": "string", ...})
                if isinstance(param_info, str):
                    param_type = param_info
                    required = True
                elif isinstance(param_info, dict):
                    param_type = param_info.get('type', 'string')
                    required = param_info.get('required', True)
                else:
                    param_type = 'string'
                    required = True
                
                req_marker = " (required)" if required else " (optional)"
                param_details.append(f'"{param_name}": <{param_type}>{req_marker}')
            
            functions_text += f"- {func_name}: {func_desc}\n"
            if param_details:
                functions_text += f"  Parameters: {{{', '.join(param_details)}}}\n"
            else:
                functions_text += f"  Parameters: none\n"
            functions_text += "\n"
        
        prompt = f"""User request: "{user_request}"

{functions_text}

Select the most appropriate function and extract parameters from the user request.

CRITICAL REQUIREMENTS:
1. Use the EXACT parameter names shown above for each function
2. DO NOT infer different parameter names
3. Extract parameter values from the user request where possible
4. For missing required parameters, make reasonable inferences from context

Return ONLY valid JSON in this format:
{{"function": "function_name", "parameters": {{"exact_param_name": "extracted_value"}}}}

Example responses:
- For get_weather with location parameter: {{"function": "get_weather", "parameters": {{"location": "Paris", "unit": "celsius"}}}}
- For send_email with recipient, subject parameters: {{"function": "send_email", "parameters": {{"recipient": "john@example.com", "subject": "Meeting reminder"}}}}"""
        
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
            # Fallback: try to extract function name at least
            func_match = re.search(r'"function":\s*"([^"]+)"', content)
            if func_match:
                return {
                    "function": func_match.group(1),
                    "parameters": {},
                    "error": f"Could not parse full response: {e}"
                }
            
            # If all else fails, return first available function
            if functions:
                return {
                    "function": functions[0].get('name', ''),
                    "parameters": {},
                    "error": f"Failed to parse LLM response, defaulted to first function: {e}"
                }
            
            return {
                "function": "",
                "parameters": {},
                "error": f"Failed to parse LLM response: {e}"
            }
    
    except Exception as e:
        return {
            "function": "",
            "parameters": {},
            "error": f"Unexpected error: {e}"
        }