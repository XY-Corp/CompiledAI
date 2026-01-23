from typing import Any, Dict, List, Optional
import asyncio
import json
import re

from pydantic import BaseModel


async def map_prompt_to_function_call(
    prompt: str,
    functions: list,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Analyzes the user prompt and available function definitions to determine which function to call and extracts the parameter values from the prompt text.
    
    Returns the function call in the format where the function name is the top-level key with parameters as nested object.
    
    Args:
        prompt: The user prompt text containing the request and values to extract
        functions: List of available function definitions, each containing name, description, and parameters schema
        
    Returns:
        Dict with function name as top-level key and extracted parameters as nested object.
        Example: {"calculate_area": {"base": 6, "height": 10, "unit": "cm"}}
    """
    try:
        # Defensive input handling - parse JSON strings if needed
        if isinstance(functions, str):
            functions = json.loads(functions)
        
        if not isinstance(functions, list):
            return {"error": f"functions must be list, got {type(functions).__name__}"}
        
        if not functions:
            return {"error": "No functions available"}
        
        # Handle None or empty prompt
        if prompt is None:
            prompt = ""
        prompt_text = str(prompt).strip()
        
        # Build detailed function descriptions with EXACT parameter names
        functions_text = "Available Functions:\n"
        function_schemas = {}
        
        for func in functions:
            func_name = func.get('name', 'unknown')
            func_desc = func.get('description', 'No description')
            
            # Handle parameters schema - check both 'parameters' and 'params' keys
            params_schema = func.get('parameters', func.get('params', {}))
            function_schemas[func_name] = params_schema
            
            functions_text += f"\nFunction: {func_name}\n"
            functions_text += f"Description: {func_desc}\n"
            
            # Extract parameter details with exact names and types
            if isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                required = params_schema.get('required', [])
                
                if properties:
                    functions_text += "Parameters (use these EXACT parameter names):\n"
                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else str(param_info)
                        param_desc = param_info.get('description', '') if isinstance(param_info, dict) else ''
                        required_marker = " (REQUIRED)" if param_name in required else " (optional)"
                        enum_values = param_info.get('enum', []) if isinstance(param_info, dict) else []
                        
                        functions_text += f'  - "{param_name}": {param_type}{required_marker}'
                        if param_desc:
                            functions_text += f' - {param_desc}'
                        if enum_values:
                            functions_text += f' [allowed values: {", ".join(str(v) for v in enum_values)}]'
                        functions_text += "\n"
        
        # Create a focused prompt for the LLM
        llm_prompt = f"""Analyze this user request and determine which function to call with what parameters.

User Request: "{prompt_text}"

{functions_text}

CRITICAL INSTRUCTIONS:
1. Select the most appropriate function based on the user request
2. Extract parameter values DIRECTLY from the user's request text
3. Use the EXACT parameter names shown above
4. For numeric values, extract as numbers (integers or floats as appropriate)
5. For units of measurement, extract them as strings (e.g., "cm", "m", "kg")
6. Return ONLY valid JSON in the exact format shown below

Return your response as JSON in this EXACT format:
{{"function_name": {{"param1": value1, "param2": value2}}}}

Example: If the function is "calculate_area" with parameters base=6, height=10, unit="cm":
{{"calculate_area": {{"base": 6, "height": 10, "unit": "cm"}}}}

Return ONLY the JSON, no explanation or markdown."""

        # Call the LLM (synchronous call - do NOT await)
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
            
            # Validate the structure - should have function name as key
            if isinstance(result, dict) and len(result) == 1:
                func_name = list(result.keys())[0]
                params = result[func_name]
                
                # Ensure params is a dict
                if isinstance(params, dict):
                    # Convert numeric strings to actual numbers where appropriate
                    cleaned_params = {}
                    for key, value in params.items():
                        if isinstance(value, str):
                            # Try to convert to int or float if it looks like a number
                            try:
                                if '.' in value:
                                    cleaned_params[key] = float(value)
                                else:
                                    cleaned_params[key] = int(value)
                            except ValueError:
                                cleaned_params[key] = value
                        else:
                            cleaned_params[key] = value
                    
                    return {func_name: cleaned_params}
            
            # If structure doesn't match, return as-is
            return result
            
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse LLM response as JSON: {e}", "raw_response": content}
            
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in functions input: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
