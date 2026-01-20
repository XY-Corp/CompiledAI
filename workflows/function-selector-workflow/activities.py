from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionSelection(BaseModel):
    """Expected structure for function selection response."""
    function: str
    parameters: dict


async def analyze_function_request(
    user_request: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes user request against available functions to select the appropriate function and extract parameters.
    
    Args:
        user_request: The natural language user request describing what the user wants to accomplish
        available_functions: List of function objects containing name and parameters schema for each available function
        
    Returns:
        Dict with function name and parameters extracted from user request
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"function": "", "parameters": {}}
            
        if not available_functions:
            return {"function": "", "parameters": {}}
        
        # Format functions with EXACT parameter names clearly visible for LLM
        functions_text = "Available Functions:\n"
        for func in available_functions:
            # Get parameters schema - handle both 'parameters' and 'params' keys
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
                    param_details.append(f'"{param_name}": <{param_type}>')
                else:
                    param_details.append(f'"{param_name}": <string>')
            
            functions_text += f"- {func['name']}: parameters must be: {{{', '.join(param_details)}}}\n"
        
        # Create clear prompt for LLM with exact parameter requirements
        prompt = f"""User request: "{user_request}"

{functions_text}

Select the most appropriate function and extract parameters from the user request.

CRITICAL: Use the EXACT parameter names shown above for each function.
DO NOT infer different parameter names.

Examples:
- For get_weather with params {{"location": "string", "unit": "string"}}: {{"function": "get_weather", "parameters": {{"location": "Paris", "unit": "celsius"}}}}
- For send_email with params {{"to": "string", "subject": "string"}}: {{"function": "send_email", "parameters": {{"to": "user@example.com", "subject": "Meeting reminder"}}}}

Return ONLY valid JSON in this exact format:
{{"function": "function_name", "parameters": {{"exact_param_name": "value"}}}}"""
        
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
            validated = FunctionSelection(**data)
            return validated.model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract function name and basic parameters
            function_match = re.search(r'"function":\s*"([^"]+)"', content)
            params_match = re.search(r'"parameters":\s*(\{[^}]*\})', content)
            
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
            
            return {"function": "", "parameters": {}}
    
    except Exception as e:
        return {"function": "", "parameters": {}}