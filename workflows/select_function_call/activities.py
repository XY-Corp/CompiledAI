from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


async def select_function_and_extract_params(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user prompt against available functions to select the appropriate function and extract its parameters.
    
    Uses LLM to understand intent and map values to the required function parameters.
    
    Args:
        prompt: The user's natural language request to analyze for function selection and parameter extraction
        functions: List of available function definitions, each containing name, description, and parameters schema
        
    Returns:
        Returns a function call object with the function name as the top-level key and its parameters as a nested object.
        Example: {"calculate_derivative": {"function": "3x^2 + 2x - 1", "x_value": 0.0}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
        # Handle empty or None prompt
        if not prompt or (isinstance(prompt, str) and prompt.strip() == ""):
            return {"error": "Empty prompt provided"}
        
        # Build function descriptions for the LLM with EXACT parameter names
        functions_text = "Available Functions:\n"
        function_schemas = {}
        
        for func in functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            
            # Handle parameters schema - check both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"\n**{func_name}**: {func_desc}\n"
            
            param_info_list = []
            param_defaults = {}
            
            # Extract parameter details with exact names and types
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                if properties:
                    functions_text += "  Parameters (use EXACT names):\n"
                    for param_name, param_info in properties.items():
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'string')
                            param_desc = param_info.get('description', '')
                            param_default = param_info.get('default', None)
                        else:
                            param_type = str(param_info)
                            param_desc = ''
                            param_default = None
                        
                        required_marker = " (required)" if param_name in required else f" (optional, default: {param_default})"
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker} - {param_desc}\n"
                        
                        param_info_list.append({
                            "name": param_name,
                            "type": param_type,
                            "required": param_name in required,
                            "default": param_default
                        })
                        if param_default is not None:
                            param_defaults[param_name] = param_default
            
            function_schemas[func_name] = {
                "params": param_info_list,
                "defaults": param_defaults
            }
        
        # Create clean prompt asking for the exact format required
        llm_prompt = f"""Analyze this user request and select the appropriate function, then extract its parameters.

User Request: "{prompt}"

{functions_text}

Instructions:
1. Select the most appropriate function based on the user's intent
2. Extract parameter values from the user's request using the EXACT parameter names shown above
3. If a parameter is optional and not mentioned in the request, omit it (the default will be applied)
4. For mathematical expressions, preserve them exactly as stated (e.g., "3x^2 + 2x - 1" or "3x**2 + 2x - 1")

Return ONLY valid JSON in this exact format (no other text):
{{"function_name": {{"param1": "value1", "param2": value2}}}}

Where function_name is replaced with the selected function name, and the nested object contains only the extracted parameters with their exact names."""

        # Call LLM to analyze and extract
        response = llm_client.generate(llm_prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse the JSON response
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                return {"error": f"Failed to parse LLM response as JSON: {content}"}
        
        # Validate result structure - should be {function_name: {params}}
        if not isinstance(result, dict):
            return {"error": f"Expected dict response, got {type(result).__name__}"}
        
        # Get the function name (should be the top-level key)
        func_names = list(result.keys())
        if not func_names:
            return {"error": "No function selected in response"}
        
        selected_func = func_names[0]
        params = result.get(selected_func, {})
        
        # Apply defaults for optional parameters if not provided
        if selected_func in function_schemas:
            defaults = function_schemas[selected_func].get("defaults", {})
            for param_name, default_value in defaults.items():
                if param_name not in params:
                    params[param_name] = default_value
        
        # Return the function call object with function name as top-level key
        return {selected_func: params}
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions input: {e}"}
    except Exception as e:
        return {"error": f"Failed to extract function call: {str(e)}"}
