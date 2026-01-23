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
    """Analyzes the user prompt to identify which function to call and extracts the parameter values.
    
    Uses LLM to understand the user's intent and map values to the correct function parameters.
    
    Args:
        prompt: The natural language user question containing the request
        functions: List of available function definitions with name, description, and parameter specifications
        
    Returns:
        A function call object with the function name as the top-level key and parameters as nested object.
        Example: {"solve_quadratic": {"a": 2, "b": 5, "c": 3}}
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
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
                
                # Handle case where schema is just properties without nested 'properties' key
                if 'type' in params_schema and params_schema.get('type') == 'dict':
                    properties = params_schema.get('properties', {})
                
                if properties:
                    functions_text += "  Parameters (use EXACT names):\n"
                    for param_name, param_info in properties.items():
                        if param_name in ('type', 'required'):
                            continue
                            
                        if isinstance(param_info, dict):
                            param_type = param_info.get('type', 'string')
                            param_desc = param_info.get('description', '')
                        else:
                            param_type = str(param_info)
                            param_desc = ''
                        
                        required_marker = " (required)" if param_name in required else ""
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker} - {param_desc}\n"
                        
                        param_types[param_name] = param_type
            
            function_param_map[func_name] = param_types
        
        # Create LLM prompt for function call extraction
        llm_prompt = f"""Analyze this user request and extract the function call parameters.

User Request: "{prompt}"

{functions_text}

INSTRUCTIONS:
1. Identify which function the user wants to call based on their request
2. Extract the parameter values from the natural language request
3. Convert values to the correct types (integers for numeric parameters)
4. Return ONLY valid JSON with the function name as the top-level key

CRITICAL: 
- Use EXACT parameter names as shown above
- For integer parameters, return actual numbers (not strings)
- Return ONLY the JSON object, no explanation

Example format:
{{"function_name": {{"param1": value1, "param2": value2}}}}

Return your JSON response:"""

        # Call LLM to extract function and parameters
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
                json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        # Find JSON object in content if not already clean
        if not content.startswith('{'):
            json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
        
        # Parse the JSON response
        result = json.loads(content)
        
        # Validate and ensure correct types based on function schema
        validated_result = {}
        for func_name, params in result.items():
            if func_name in function_param_map:
                validated_params = {}
                param_types = function_param_map[func_name]
                
                for param_name, param_value in params.items():
                    expected_type = param_types.get(param_name, 'string')
                    
                    # Convert to correct type
                    if expected_type in ('integer', 'int', 'number'):
                        if isinstance(param_value, str):
                            validated_params[param_name] = int(param_value)
                        else:
                            validated_params[param_name] = int(param_value)
                    elif expected_type == 'float':
                        validated_params[param_name] = float(param_value)
                    elif expected_type == 'boolean':
                        validated_params[param_name] = bool(param_value)
                    else:
                        validated_params[param_name] = param_value
                
                validated_result[func_name] = validated_params
            else:
                validated_result[func_name] = params
        
        return validated_result
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse LLM response as JSON: {e}"}
    except Exception as e:
        return {"error": f"Error extracting function call: {str(e)}"}
