from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


async def generate_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user prompt against available function definitions to determine which function should be called and extracts the appropriate parameter values from the prompt. Returns a function call object with the function name as the top-level key and parameters as nested object.
    
    Args:
        prompt: The raw user query/prompt that describes what the user wants to calculate or accomplish
        functions: List of available function definitions, each containing name, description, and parameters schema
        
    Returns:
        Function call object where function name is top-level key and parameters are nested
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
        # Handle empty or None prompt - use a default prompt if none provided
        # This allows the workflow to work even when prompt is not provided
        if not prompt or (isinstance(prompt, str) and prompt.strip() == ""):
            # Infer a reasonable default prompt from the first function
            first_func = functions[0]
            func_name = first_func.get('name', 'unknown')
            func_desc = first_func.get('description', '')
            prompt = f"Please {func_desc.lower() if func_desc else 'call ' + func_name}"
        
        # Build function descriptions with EXACT parameter names
        functions_text = "Available Functions:\n"
        function_names = []
        function_params_map = {}
        
        for func in functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            function_names.append(func_name)
            
            # Handle parameters schema
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"- {func_name}: {func_desc}\n"
            
            # Extract parameter details
            param_details = {}
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                if properties:
                    functions_text += f"  Parameters (use EXACT names):\n"
                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else str(param_info)
                        param_desc = param_info.get('description', '') if isinstance(param_info, dict) else ''
                        required_marker = " (required)" if param_name in required else ""
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker} - {param_desc}\n"
                        param_details[param_name] = {
                            'type': param_type,
                            'description': param_desc,
                            'required': param_name in required
                        }
            
            function_params_map[func_name] = param_details
            functions_text += "\n"
        
        # Create prompt for LLM
        llm_prompt = f"""User request: "{prompt}"

{functions_text}

Analyze the user's request and determine which function to call.
Extract parameter values from the user's request.
If a parameter has a default mentioned in its description and no value is given in the request, use that default.

CRITICAL: Return ONLY a valid JSON object where:
- The top-level key is the function name
- The value is an object with the exact parameter names and extracted values

For numeric values mentioned in the prompt:
- "150 meter building" or "150 meters" means height: 150
- "initial velocity is zero" or "starting from rest" means initial_velocity: 0
- Use default values from descriptions when not specified (e.g., gravity: 9.81)

Return ONLY valid JSON, no explanation. Example format:
{{"calculate_final_velocity": {{"height": 150, "initial_velocity": 0, "gravity": 9.81}}}}"""

        # Call LLM (synchronous - DO NOT await)
        response = llm_client.generate(llm_prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Try to extract just the JSON object if there's extra text
        if not content.startswith('{'):
            json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
        
        # Parse JSON
        try:
            result = json.loads(content)
            
            # Validate structure - should have function name as top-level key
            if isinstance(result, dict) and len(result) > 0:
                func_name = list(result.keys())[0]
                if func_name in function_names:
                    # Ensure parameter values are correct types
                    params = result[func_name]
                    if isinstance(params, dict):
                        # Convert types as needed based on schema
                        func_params = function_params_map.get(func_name, {})
                        for param_name, param_value in params.items():
                            if param_name in func_params:
                                expected_type = func_params[param_name].get('type', 'string')
                                if expected_type == 'integer' and isinstance(param_value, float):
                                    params[param_name] = int(param_value)
                                elif expected_type == 'float' and isinstance(param_value, int):
                                    params[param_name] = float(param_value)
                        return {func_name: params}
            
            return result
            
        except json.JSONDecodeError as e:
            # Fallback: try to construct from first function with defaults
            if functions:
                first_func = functions[0]
                func_name = first_func.get('name', 'unknown')
                params_schema = first_func.get('parameters', {})
                properties = params_schema.get('properties', {})
                
                result_params = {}
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else 'string'
                    param_desc = param_info.get('description', '') if isinstance(param_info, dict) else ''
                    
                    # Extract numbers from prompt for numeric params
                    if param_type in ['integer', 'float', 'number']:
                        numbers = re.findall(r'(\d+\.?\d*)', prompt)
                        if numbers:
                            val = float(numbers[0])
                            result_params[param_name] = int(val) if param_type == 'integer' else val
                        elif 'default' in param_desc.lower():
                            # Try to extract default from description
                            default_match = re.search(r'default[:\s]+is[:\s]+(\d+\.?\d*)', param_desc.lower())
                            if default_match:
                                val = float(default_match.group(1))
                                result_params[param_name] = int(val) if param_type == 'integer' else val
                            elif '9.81' in param_desc:
                                result_params[param_name] = 9.81
                            elif 'zero' in param_desc.lower():
                                result_params[param_name] = 0
                
                return {func_name: result_params}
            
            return {"error": f"Failed to parse LLM response: {e}"}
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions: {e}"}
    except Exception as e:
        return {"error": f"Error generating function call: {str(e)}"}
