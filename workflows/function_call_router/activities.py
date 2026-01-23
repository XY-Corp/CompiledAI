from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


async def route_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user prompt and available function definitions to determine which function 
    should be called and extracts the parameter values from the natural language request.
    
    Args:
        prompt: The natural language user request containing the action to perform and parameter values
        functions: List of available function definitions, each containing name, description, and parameter schemas
        
    Returns:
        A function call object with the function name as the top-level key and extracted parameters 
        as nested object. Example: {"calculate_triangle_area": {"base": 10, "height": 5, "unit": "units"}}
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
        function_param_map = {}
        
        for func in functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            
            # Handle parameters schema - check both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"\n**{func_name}**: {func_desc}\n"
            
            param_types = {}
            
            # Extract parameter details with exact names and types
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', params_schema)
                required = params_schema.get('required', [])
                
                # Handle case where params_schema is the properties directly (no 'properties' wrapper)
                if 'type' in params_schema and params_schema.get('type') == 'dict':
                    properties = params_schema.get('properties', {})
                
                if properties:
                    functions_text += "  Parameters (use EXACT names):\n"
                    for param_name, param_info in properties.items():
                        if param_name in ['type', 'required']:
                            continue
                            
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'string')
                            param_desc = param_info.get('description', '')
                            param_default = param_info.get('default', None)
                            param_enum = param_info.get('enum', None)
                        else:
                            param_type = str(param_info)
                            param_desc = ''
                            param_default = None
                            param_enum = None
                        
                        is_required = param_name in required if required else False
                        required_marker = " (required)" if is_required else ""
                        if param_default is not None and not is_required:
                            required_marker = f" (optional, default: {param_default})"
                        enum_text = f", allowed values: {param_enum}" if param_enum else ""
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker} - {param_desc}{enum_text}\n"
                        
                        param_types[param_name] = param_type
            
            function_param_map[func_name] = param_types
        
        # Create the prompt for function selection and parameter extraction
        llm_prompt = f"""Analyze this user request and determine which function to call with what parameters.

User Request: "{prompt}"

{functions_text}

Instructions:
1. Select the most appropriate function based on the user's request
2. Extract parameter values from the user's natural language request
3. Use EXACT parameter names as shown above for the selected function
4. Convert values to appropriate types (numbers should be numbers, not strings)
5. If a parameter value is not explicitly mentioned, use a reasonable default based on context

Return ONLY valid JSON in this exact format:
{{"function_name": {{"param1": value1, "param2": value2}}}}

Where "function_name" is replaced with the actual selected function name, and parameters use exact names from the function definition.

Example: If the function is "calculate_area" with parameters "width" and "height", return:
{{"calculate_area": {{"width": 10, "height": 5}}}}"""

        # Call LLM to analyze the prompt and extract function call
        response = llm_client.generate(llm_prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            # Extract content between ```json and ``` or between ``` and ```
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        else:
            # Try to find JSON object in plain text
            json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
        
        # Parse the JSON response
        result = json.loads(content)
        
        # Validate the structure - should have exactly one function key with dict value
        if not isinstance(result, dict):
            return {"error": "Invalid response structure from LLM"}
        
        # Get the function name (should be the only key at top level)
        function_keys = [k for k in result.keys() if k != "error"]
        if len(function_keys) != 1:
            return {"error": f"Expected exactly one function key, got {len(function_keys)}"}
        
        function_name = function_keys[0]
        parameters = result[function_name]
        
        # Ensure parameters is a dict
        if not isinstance(parameters, dict):
            return {"error": f"Parameters must be a dict, got {type(parameters).__name__}"}
        
        # Validate function name exists in available functions
        available_func_names = [f.get('name') for f in functions]
        if function_name not in available_func_names:
            return {"error": f"Selected function '{function_name}' not in available functions"}
        
        # Type conversion for numeric parameters based on function schema
        if function_name in function_param_map:
            expected_types = function_param_map[function_name]
            for param_name, param_value in parameters.items():
                if param_name in expected_types:
                    expected_type = expected_types[param_name]
                    if expected_type in ('integer', 'int') and isinstance(param_value, str):
                        try:
                            parameters[param_name] = int(param_value)
                        except ValueError:
                            pass
                    elif expected_type in ('number', 'float') and isinstance(param_value, str):
                        try:
                            parameters[param_name] = float(param_value)
                        except ValueError:
                            pass
        
        # Return in the exact format specified: {"function_name": {"param": value}}
        return {function_name: parameters}
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse LLM response as JSON: {e}"}
    except Exception as e:
        return {"error": f"Error routing function call: {str(e)}"}
