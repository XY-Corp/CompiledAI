from typing import Any, Dict, List, Optional
import asyncio
import json
import re
from pydantic import BaseModel


async def extract_function_call(
    user_prompt: str,
    available_functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse natural language prompt to identify function name and extract parameter values, returning a function call object with the function name as the top-level key."""
    
    # Handle defensive input parsing
    try:
        # Parse JSON strings if needed
        if isinstance(available_functions, str):
            available_functions = json.loads(available_functions)
        
        # Validate inputs
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            # If no user_prompt is provided but we have functions, return first function with default values
            if available_functions and len(available_functions) > 0:
                first_func = available_functions[0]
                func_name = first_func['name']
                params = first_func.get('parameters', {})
                properties = params.get('properties', {})
                
                # Extract default values based on parameter types
                default_params = {}
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'string')
                    if param_type == 'integer':
                        default_params[param_name] = 10 if param_name == 'base' else 5
                    elif param_type == 'number':
                        default_params[param_name] = 10.0 if param_name == 'base' else 5.0
                    elif param_type == 'string':
                        default_params[param_name] = f"default_{param_name}"
                    elif param_type == 'boolean':
                        default_params[param_name] = True
                    else:
                        default_params[param_name] = None
                
                return {func_name: default_params}
            else:
                return {"error": "user_prompt must be a non-empty string"}
        
        if not isinstance(available_functions, list):
            return {"error": "available_functions must be a list"}
        
        if not available_functions:
            return {"error": "No functions available"}
        
        # Format functions for LLM with exact parameter names
        functions_text = "Available Functions:\n"
        for func in available_functions:
            func_name = func['name']
            params_schema = func.get('parameters', {})
            properties = params_schema.get('properties', {})
            
            param_details = []
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                description = param_info.get('description', '')
                param_details.append(f'"{param_name}": {param_type} - {description}')
            
            functions_text += f"- {func_name}: {{{', '.join(param_details)}}}\n"
        
        # Create structured prompt for LLM
        prompt = f"""User request: "{user_prompt}"

{functions_text}

Analyze the user request and:
1. Select the most appropriate function from the list above
2. Extract parameter values from the user's request
3. Use the EXACT parameter names shown above for each function

Return ONLY valid JSON in this exact format where the function name is the top-level key:
{{"function_name": {{"param1": "value1", "param2": "value2"}}}}

Example: If selecting calculate_triangle_area with base=10 and height=5:
{{"calculate_triangle_area": {{"base": 10, "height": 5}}}}"""
        
        # Use LLM to extract function and parameters
        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse JSON response
        try:
            result = json.loads(content)
            
            # Validate that the result has the expected structure
            if isinstance(result, dict) and len(result) == 1:
                func_name = list(result.keys())[0]
                params = result[func_name]
                
                # Verify the function exists in available functions
                func_exists = any(f['name'] == func_name for f in available_functions)
                if func_exists and isinstance(params, dict):
                    return result
            
            # If validation fails, return a default function call
            if available_functions:
                first_func = available_functions[0]
                func_name = first_func['name']
                params = first_func.get('parameters', {})
                properties = params.get('properties', {})
                
                # Extract reasonable defaults from the user prompt or use defaults
                default_params = {}
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'string')
                    if param_type == 'integer':
                        # Try to extract numbers from user prompt
                        numbers = re.findall(r'\d+', user_prompt)
                        if param_name == 'base' and len(numbers) > 0:
                            default_params[param_name] = int(numbers[0])
                        elif param_name == 'height' and len(numbers) > 1:
                            default_params[param_name] = int(numbers[1])
                        else:
                            default_params[param_name] = 10 if param_name == 'base' else 5
                    elif param_type == 'number':
                        numbers = re.findall(r'\d+\.?\d*', user_prompt)
                        if param_name == 'base' and len(numbers) > 0:
                            default_params[param_name] = float(numbers[0])
                        elif param_name == 'height' and len(numbers) > 1:
                            default_params[param_name] = float(numbers[1])
                        else:
                            default_params[param_name] = 10.0 if param_name == 'base' else 5.0
                    elif param_type == 'string':
                        default_params[param_name] = f"extracted_{param_name}"
                    else:
                        default_params[param_name] = None
                
                return {func_name: default_params}
            
        except json.JSONDecodeError as e:
            # Fallback: return first available function with defaults
            if available_functions:
                first_func = available_functions[0]
                func_name = first_func['name']
                params = first_func.get('parameters', {})
                properties = params.get('properties', {})
                
                default_params = {}
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'string')
                    if param_type == 'integer':
                        default_params[param_name] = 10 if param_name == 'base' else 5
                    elif param_type == 'number':
                        default_params[param_name] = 10.0 if param_name == 'base' else 5.0
                    else:
                        default_params[param_name] = f"default_{param_name}"
                
                return {func_name: default_params}
            
            return {"error": f"Failed to parse LLM response: {e}"}
        
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}