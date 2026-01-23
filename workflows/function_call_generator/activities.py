from typing import Any, Dict, List, Optional
import json
import re


async def generate_function_call(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user prompt to identify the appropriate function to call and extracts the required parameters from the prompt.
    
    Returns a function call object with the function name as the top-level key and parameters as nested object.
    
    Args:
        user_prompt: The user's natural language query/request that needs to be parsed to identify intent and extract parameter values
        available_functions: List of function definition objects, each containing 'name', 'description', and 'parameters' fields
        
    Returns:
        A function call object with the function name as the top-level key and its parameters as a nested object.
        Example: {"get_prime_factors": {"number": 450, "formatted": true}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        if not isinstance(available_functions, list):
            return {"error": f"available_functions must be list, got {type(available_functions).__name__}"}
        
        if not available_functions:
            return {"error": "No functions available"}
        
        # Handle empty or None prompt
        if not user_prompt or (isinstance(user_prompt, str) and user_prompt.strip() == ""):
            return {"error": "user_prompt is empty or not provided"}
        
        # Build function descriptions for the LLM with EXACT parameter names
        functions_text = "Available Functions:\n"
        function_param_info = {}
        
        for func in available_functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            
            # Handle parameters schema - check both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"\n**{func_name}**: {func_desc}\n"
            
            param_info_list = []
            
            # Extract parameter details with exact names and types
            if isinstance(params_schema, dict):
                # Handle both flat dict format and nested 'properties' format
                properties = params_schema.get('properties', {})
                if not properties and params_schema.get('type') != 'dict':
                    # Flat format: {"param_name": {"type": "...", ...}}
                    properties = {k: v for k, v in params_schema.items() if k not in ('type', 'required')}
                
                required = params_schema.get('required', [])
                
                if properties:
                    functions_text += "  Parameters (use EXACT names):\n"
                    for param_name, param_def in properties.items():
                        if isinstance(param_def, dict):
                            param_type = param_def.get('type', 'string')
                            param_desc = param_def.get('description', '')
                            param_default = param_def.get('default', None)
                            param_enum = param_def.get('enum', None)
                        else:
                            param_type = str(param_def)
                            param_desc = ''
                            param_default = None
                            param_enum = None
                        
                        required_marker = " (required)" if param_name in required else ""
                        default_text = f" (default: {param_default})" if param_default is not None else ""
                        enum_text = f", allowed values: {param_enum}" if param_enum else ""
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker}{default_text} - {param_desc}{enum_text}\n"
                        
                        param_info_list.append({
                            "name": param_name,
                            "type": param_type,
                            "default": param_default
                        })
            
            function_param_info[func_name] = param_info_list
        
        # Create prompt for the LLM
        llm_prompt = f"""Analyze this user request and determine which function to call and what parameters to extract.

User Request: "{user_prompt}"

{functions_text}

Instructions:
1. Select the most appropriate function based on the user's intent
2. Extract parameter values from the user request
3. Use EXACT parameter names as shown above
4. For boolean parameters, default to true if not explicitly mentioned
5. Convert extracted values to appropriate types (numbers should be integers/floats, not strings)

Return ONLY valid JSON in this exact format:
{{"function_name": {{"param1": value1, "param2": value2}}}}

Where "function_name" is replaced with the actual selected function name.

Example: If user says "Find prime factors of 450" and function is get_prime_factors with params number and formatted:
{{"get_prime_factors": {{"number": 450, "formatted": true}}}}

Return ONLY the JSON, no explanation."""

        # Call the LLM (synchronous - do NOT await)
        response = llm_client.generate(llm_prompt)
        
        # Extract JSON from response
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse the JSON response
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON more aggressively
            json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                return {"error": f"Failed to parse LLM response as JSON: {content}"}
        
        # Validate the result structure - should be {function_name: {params}}
        if not isinstance(result, dict):
            return {"error": f"Expected dict result, got {type(result).__name__}"}
        
        if len(result) != 1:
            return {"error": "Result should contain exactly one function call"}
        
        func_name = list(result.keys())[0]
        params = result[func_name]
        
        if not isinstance(params, dict):
            return {"error": f"Parameters should be a dict, got {type(params).__name__}"}
        
        # Return the function call object directly (function name as key, params as value)
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in input: {e}"}
    except Exception as e:
        return {"error": f"Error processing request: {str(e)}"}
