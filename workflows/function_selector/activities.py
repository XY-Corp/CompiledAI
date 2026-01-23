from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


class FunctionSelection(BaseModel):
    """Model for validating function selection output."""
    function: str
    parameters: dict


async def analyze_user_request(
    prompt_data: str,
    available_functions: list,
    user_request_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user request to determine which function to call and what parameters to extract.
    
    Args:
        prompt_data: The complete prompt data containing template, functions, and user request information
        available_functions: List of function definitions with names and parameter schemas that can be called
        user_request_text: The natural language user request that needs to be mapped to a function call
        
    Returns:
        Dict containing function selection result with structure: {"function": "function_name", "parameters": {...}}
    """
    try:
        # Handle JSON string input defensively for available_functions
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate that we have functions to work with
        if not isinstance(available_functions, list) or len(available_functions) == 0:
            return {"function": "", "parameters": {}}
        
        # Build comprehensive prompt with exact parameter names
        functions_text = "Available Functions:\n"
        for func in available_functions:
            func_name = func.get('name', '')
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
                    param_details.append(f'"{param_name}": <{param_type}>')
                else:
                    param_details.append(f'"{param_name}": <string>')
            
            params_str = ', '.join(param_details)
            functions_text += f"- {func_name}: parameters must be: {{{params_str}}}\n"
            
            # Add description if available
            if 'description' in func:
                functions_text += f"  Description: {func['description']}\n"
        
        # Create clear prompt for LLM
        prompt = f"""User request: "{user_request_text}"

{functions_text}

Select the most appropriate function for this user request and extract the required parameters.

CRITICAL RULES:
1. Use the EXACT parameter names shown above for the selected function
2. DO NOT infer different parameter names
3. Extract actual values from the user request for each parameter
4. If a required parameter cannot be determined from the request, use a reasonable default or leave as empty string

Return ONLY valid JSON in this exact format:
{{"function": "function_name", "parameters": {{"exact_param_name": "extracted_value"}}}}

Example for get_weather function:
{{"function": "get_weather", "parameters": {{"location": "Paris", "unit": "celsius"}}}}"""

        # Use LLM to analyze request and select function
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            # Extract content between ```json and ``` or between ``` and ```
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse and validate JSON response
        try:
            data = json.loads(content)
            validated = FunctionSelection(**data)
            return validated.model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract function and parameters manually
            function_name = ""
            parameters = {}
            
            # Try to match function name from available functions
            for func in available_functions:
                func_name = func.get('name', '')
                if func_name.lower() in user_request_text.lower():
                    function_name = func_name
                    break
            
            # If no function matched, use the first one as fallback
            if not function_name and available_functions:
                function_name = available_functions[0].get('name', '')
            
            return {
                "function": function_name,
                "parameters": parameters
            }
            
    except Exception as e:
        # Return empty result if everything fails
        return {
            "function": "",
            "parameters": {}
        }