from typing import Any, Dict, List, Optional
import json
import re
from pydantic import BaseModel


async def extract_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse a natural language prompt to identify which function should be called and extract the parameter values.
    
    Uses LLM to understand the user's intent and map it to the appropriate function from the provided function list.
    
    Args:
        prompt: The natural language user query containing the request
        functions: List of available function definitions, each containing name, description, and parameters schema
        
    Returns:
        A function call object with the function name as the top-level key and parameters as nested object.
        Example: {"calculate_triangle_area": {"base": 10, "height": 5}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
        # Handle empty prompt
        if not prompt or (isinstance(prompt, str) and prompt.strip() == ""):
            return {"error": "No prompt provided"}
        
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
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                # Handle case where params_schema has direct properties (not nested under 'properties')
                if not properties and params_schema.get('type') == 'dict':
                    # Check if there are property definitions directly
                    properties = {k: v for k, v in params_schema.items() if k not in ['type', 'required', 'description']}
                
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
                        
                        param_types[param_name] = param_type
            
            function_param_map[func_name] = param_types
        
        # Create clean prompt asking for the exact format required
        llm_prompt = f"""Analyze this user request and extract the function call parameters.

User Request: "{prompt}"

{functions_text}

INSTRUCTIONS:
1. Identify which function the user wants to call based on their request
2. Extract the parameter values from the natural language text
3. Convert values to appropriate types (numbers should be integers/floats, not strings)

CRITICAL: Return ONLY a JSON object with the function name as the top-level key and parameters as a nested object.

Example format:
{{"function_name": {{"param1": value1, "param2": value2}}}}

For a request like "What is the area of a triangle with base of 10 units and height of 5 units?":
{{"calculate_triangle_area": {{"base": 10, "height": 5}}}}

Return ONLY the JSON object, no explanation or markdown."""

        # Call LLM (synchronous, not async)
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
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Parse the JSON response
        try:
            result = json.loads(content)
            
            # Validate structure - should have function name as top-level key
            if isinstance(result, dict) and len(result) > 0:
                # Get the function name (first key)
                func_name = list(result.keys())[0]
                
                # Ensure parameter values are proper types (convert strings to numbers where needed)
                if func_name in function_param_map and isinstance(result[func_name], dict):
                    params = result[func_name]
                    expected_types = function_param_map[func_name]
                    
                    for param_name, param_value in params.items():
                        if param_name in expected_types:
                            expected_type = expected_types[param_name]
                            if expected_type in ['integer', 'int'] and isinstance(param_value, str):
                                try:
                                    params[param_name] = int(param_value)
                                except ValueError:
                                    pass
                            elif expected_type in ['number', 'float'] and isinstance(param_value, str):
                                try:
                                    params[param_name] = float(param_value)
                                except ValueError:
                                    pass
                
                return result
            else:
                return {"error": "Invalid response format from LLM"}
                
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse LLM response: {e}"}
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
