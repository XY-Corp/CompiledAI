from typing import Any, Dict, List, Optional
import json
import re


async def extract_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse the natural language prompt and extract parameter values to construct a function call object.
    
    Uses LLM to understand the intent and extract the correct values, then formats them
    according to the function schema.
    
    Args:
        prompt: The natural language prompt containing the task description with parameter values
                to be extracted (e.g., 'Solve a quadratic equation where a=2, b=6, and c=5')
        functions: List of available function definitions, each containing name, description,
                   and parameters schema with types and required fields
        
    Returns:
        A function call object with the function name as the top-level key and parameters
        as nested object. Example: {"solve_quadratic_equation": {"a": 2, "b": 6, "c": 5}}
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
                # Handle nested properties structure
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                # If no 'properties' key, treat the dict itself as parameters
                if not properties and 'type' not in params_schema:
                    properties = params_schema
                elif not properties and params_schema.get('type') == 'dict':
                    # Look for properties in a nested structure
                    properties = params_schema.get('properties', params_schema)
                
                if properties:
                    functions_text += "  Parameters (use EXACT names):\n"
                    for param_name, param_info in properties.items():
                        if param_name == 'type':
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
        
        # Create clean prompt asking for the exact format required
        llm_prompt = f"""Analyze this user request and extract the function call parameters.

User Request: "{prompt}"

{functions_text}

Instructions:
1. Identify which function best matches the user's request
2. Extract the parameter values from the user request
3. Use the EXACT parameter names as shown above
4. Return ONLY valid JSON with the function name as the top-level key

Return format (no other text, just JSON):
{{"function_name": {{"param1": value1, "param2": value2}}}}

For numeric parameters (integer, int, number), return actual numbers without quotes.
For string parameters, return strings with quotes.

Example: If user says "Solve a quadratic equation where a=2, b=6, and c=5" for solve_quadratic_equation:
{{"solve_quadratic_equation": {{"a": 2, "b": 6, "c": 5}}}}

Your response (ONLY JSON):"""

        # Call LLM (synchronous - do NOT await)
        response = llm_client.generate(llm_prompt)
        
        # Extract JSON from response
        content = response.content.strip()
        
        # Remove markdown code blocks if present
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
        except json.JSONDecodeError:
            # Try to extract JSON from the content more aggressively
            json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                return {"error": f"Failed to parse LLM response as JSON: {content}"}
        
        # Validate and ensure proper types based on function schema
        if isinstance(result, dict) and len(result) == 1:
            func_name = list(result.keys())[0]
            params = result[func_name]
            
            # Apply type coercion based on function schema
            if func_name in function_param_map:
                expected_types = function_param_map[func_name]
                coerced_params = {}
                
                for param_name, param_value in params.items():
                    expected_type = expected_types.get(param_name, 'string')
                    
                    # Coerce types based on schema
                    if expected_type in ('integer', 'int'):
                        try:
                            coerced_params[param_name] = int(param_value)
                        except (ValueError, TypeError):
                            coerced_params[param_name] = param_value
                    elif expected_type in ('number', 'float'):
                        try:
                            coerced_params[param_name] = float(param_value)
                        except (ValueError, TypeError):
                            coerced_params[param_name] = param_value
                    elif expected_type == 'boolean':
                        if isinstance(param_value, str):
                            coerced_params[param_name] = param_value.lower() in ('true', '1', 'yes')
                        else:
                            coerced_params[param_name] = bool(param_value)
                    else:
                        coerced_params[param_name] = param_value
                
                return {func_name: coerced_params}
        
        return result
        
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions: {e}"}
    except Exception as e:
        return {"error": f"Extraction failed: {str(e)}"}
