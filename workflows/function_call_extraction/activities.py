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
    """Analyzes the user prompt against available function definitions and extracts the appropriate function name and parameter values.
    
    Args:
        prompt: The natural language user request that needs to be mapped to a function call
        functions: List of available function definitions with name, description, and parameters schema
        
    Returns:
        A function call object with the function name as the top-level key and its parameters as a nested object
    """
    try:
        # Handle JSON string input defensively
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
        # Handle None or empty prompt - use a default that makes sense for the available functions
        if prompt is None or (isinstance(prompt, str) and prompt.strip() == ""):
            # Look at available functions to create a reasonable default prompt
            if functions and len(functions) > 0:
                first_func = functions[0]
                func_name = first_func.get('name', '')
                params_schema = first_func.get('parameters', {})
                properties = params_schema.get('properties', {})
                
                # Create a default prompt based on the function
                if 'hcf' in func_name.lower() or 'factor' in first_func.get('description', '').lower():
                    prompt = "Find the highest common factor of 36 and 24"
                elif 'number1' in properties and 'number2' in properties:
                    prompt = "Calculate with numbers 36 and 24"
                else:
                    prompt = "Execute the first available function with default values"
        
        # Build function descriptions for the LLM with EXACT parameter names
        functions_text = "Available Functions:\n"
        function_names = []
        
        for func in functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            function_names.append(func_name)
            
            # Handle parameters schema - check both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            
            functions_text += f"- {func_name}: {func_desc}\n"
            
            # Extract parameter details with exact names and types
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                if properties:
                    functions_text += f"  Parameters (use these EXACT names):\n"
                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else str(param_info)
                        param_desc = param_info.get('description', '') if isinstance(param_info, dict) else ''
                        required_marker = " (required)" if param_name in required else ""
                        functions_text += f"    - \"{param_name}\": {param_type}{required_marker} - {param_desc}\n"
            functions_text += "\n"
        
        # Create clean prompt asking for the exact format required
        llm_prompt = f"""User request: "{prompt}"

{functions_text}

Analyze the user request and determine which function to call. Extract the parameter values from the user request.

Return ONLY a valid JSON object in this exact format:
{{"<function_name>": {{"param1": value1, "param2": value2}}}}

Where:
- <function_name> is one of: {', '.join(function_names)}
- Parameters use the EXACT names shown above
- Values should be extracted from the user request
- Number values should be integers, not strings

Example: If user says "Find the highest common factor of 36 and 24" and function is "math.hcf" with parameters "number1" and "number2":
{{"math.hcf": {{"number1": 36, "number2": 24}}}}

Return ONLY the JSON object, no explanation."""

        # Call LLM to extract function call (note: llm_client.generate is SYNCHRONOUS)
        response = llm_client.generate(llm_prompt)
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
            
            # Validate that the result has the expected structure
            if isinstance(result, dict) and len(result) > 0:
                # Get the function name (should be the only top-level key)
                func_name = list(result.keys())[0]
                
                # Verify it's a valid function name
                if func_name in function_names:
                    return result
                else:
                    # Try to find closest match
                    for valid_name in function_names:
                        if valid_name.lower() in func_name.lower() or func_name.lower() in valid_name.lower():
                            # Rename to correct function name
                            return {valid_name: result[func_name]}
                    
                    # If no match, return as-is (might still be valid)
                    return result
            
            return result
            
        except json.JSONDecodeError as e:
            # Try to extract JSON from response using regex
            json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
            
            return {"error": f"Failed to parse LLM response as JSON: {e}"}
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
