from typing import Any, Dict, List, Optional
import json
import re


async def select_function_and_extract_params(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes a user prompt against available function definitions to select the appropriate function and extract parameter values.
    
    Returns the function name as the top-level key with its parameters as a nested object.
    
    Args:
        prompt: The natural language user request to analyze
        functions: List of available function definitions with name, description, and parameters schema
        
    Returns:
        Dict with function name as top-level key and parameters as nested object.
        Example: {"geometry.circumference": {"radius": 3, "units": "cm"}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
        # Build function descriptions for the LLM with EXACT parameter names
        functions_text = "Available Functions:\n"
        function_details = {}
        
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
                            param_enum = param_info.get('enum', None)
                        else:
                            param_type = str(param_info)
                            param_desc = ''
                            param_default = None
                            param_enum = None
                        
                        required_marker = " (REQUIRED)" if param_name in required else f" (optional, default: {param_default})"
                        enum_text = f", allowed values: {param_enum}" if param_enum else ""
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker} - {param_desc}{enum_text}\n"
                        
                        param_info_list.append({
                            'name': param_name,
                            'type': param_type,
                            'required': param_name in required,
                            'default': param_default
                        })
                        
                        if param_default is not None:
                            param_defaults[param_name] = param_default
            
            function_details[func_name] = {
                'params': param_info_list,
                'defaults': param_defaults
            }
        
        # Create the LLM prompt for function selection and parameter extraction
        llm_prompt = f"""Analyze this user request and determine which function to call with what parameters.

User Request: "{prompt}"

{functions_text}

INSTRUCTIONS:
1. Select the most appropriate function based on the user's request
2. Extract parameter values from the user's request
3. Use EXACT parameter names as shown above
4. For optional parameters not mentioned, use the default value
5. Convert numeric values to integers or floats as appropriate for the parameter type

Return ONLY valid JSON in this exact format (no other text):
{{"<function_name>": {{"<param1>": <value1>, "<param2>": <value2>}}}}

Example for geometry.circumference with radius 5:
{{"geometry.circumference": {{"radius": 5, "units": "cm"}}}}"""

        # Call the LLM
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
            # Try to extract JSON object directly
            json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
        
        # Parse the JSON response
        result = json.loads(content)
        
        # Validate structure and apply defaults
        if isinstance(result, dict) and len(result) == 1:
            func_name = list(result.keys())[0]
            params = result[func_name]
            
            # Ensure params is a dict
            if not isinstance(params, dict):
                params = {}
            
            # Apply defaults for missing optional parameters
            if func_name in function_details:
                defaults = function_details[func_name]['defaults']
                for default_param, default_value in defaults.items():
                    if default_param not in params:
                        params[default_param] = default_value
            
            # Return the properly formatted result
            return {func_name: params}
        
        # If structure is unexpected, return as-is
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse LLM response as JSON: {e}"}
    except Exception as e:
        return {"error": f"Error processing request: {str(e)}"}
